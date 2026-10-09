import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from forum.services.schedule_services import (
    _events_require_ceremonial_uniform,
    get_alt_day_event,
    get_block_order_for_day,
    get_calendar_events_for_day,
    get_sheet_row_data,
)


class ScheduleCalendarTests(SimpleTestCase):
    @patch('forum.services.schedule_services.load_row_from_cache', return_value=None)
    @patch('forum.services.schedule_services._get_schedule_sheet')
    def test_missing_row_cache_looks_up_date_in_sheet(self, get_sheet, _load_cache):
        sheet = get_sheet.return_value
        sheet.col_values.return_value = ['header'] * 6 + ['Fri, Sep 25']
        sheet.get_all_values.return_value = [['header']] * 6 + [['Fri, Sep 25', '1A']]

        with patch('forum.services.schedule_services._sheet_data', None):
            self.assertEqual(get_sheet_row_data('Fri, Sep 25'), ['Fri, Sep 25', '1A'])
        sheet.col_values.assert_called_once()

    @patch('forum.services.schedule_services.load_row_from_cache', return_value=None)
    @patch('forum.services.schedule_services._get_schedule_sheet')
    def test_sheet_failure_does_not_look_like_no_school(self, get_sheet, _load_cache):
        get_sheet.return_value.col_values.side_effect = ConnectionError('unavailable')
        with patch('forum.services.schedule_services._sheet_data', None):
            with self.assertRaises(ConnectionError):
                get_sheet_row_data('Fri, Sep 25')

    @patch('forum.services.schedule_services.google_api_service.get_calendar_service')
    def test_calendar_response_is_shared_by_all_daily_checks(self, get_calendar_service):
        events = [{
            'summary': 'Alt Day - Early Dismissal',
            'description': '8:30-9:30\nCeremonial Uniform',
            'start': {'date': '2026-09-25'},
        }]
        execute = Mock(return_value={'items': events})
        get_calendar_service.return_value.events.return_value.list.return_value.execute = execute
        calendar_context = {}
        target_date = datetime.date(2026, 9, 25)

        first_result = get_calendar_events_for_day(target_date, calendar_context)
        second_result = get_calendar_events_for_day(target_date, calendar_context)
        alt_day_event = get_alt_day_event(first_result, target_date)

        self.assertIs(first_result, second_result)
        self.assertEqual(alt_day_event['summary'], 'Alt Day - Early Dismissal')
        self.assertTrue(_events_require_ceremonial_uniform(second_result))
        execute.assert_called_once_with()

    @patch('forum.services.schedule_services.google_api_service.get_calendar_service')
    def test_calendar_query_uses_complete_vancouver_day_across_dst(self, get_calendar_service):
        get_calendar_service.return_value.events.return_value.list.return_value.execute.return_value = {'items': []}

        get_calendar_events_for_day(datetime.date(2026, 3, 8))

        kwargs = get_calendar_service.return_value.events.return_value.list.call_args.kwargs
        self.assertEqual(kwargs['timeMin'], '2026-03-08T00:00:00-08:00')
        self.assertEqual(kwargs['timeMax'], '2026-03-09T00:00:00-07:00')

    def test_previous_day_alt_event_is_ignored(self):
        events = [
            {'summary': 'Alt Day - yesterday', 'start': {'date': '2026-10-04'}},
            {'summary': 'Alt Day - today', 'start': {'date': '2026-10-05'}},
        ]

        self.assertIs(get_alt_day_event(events, datetime.date(2026, 10, 5)), events[1])

    @patch('forum.services.schedule_services.DailySchedule')
    @patch('forum.services.schedule_services.get_calendar_events_for_day', return_value=None)
    @patch('forum.services.schedule_services.get_sheet_row_data', return_value=['', '', '', '', '1A', '1B', '1C', '1D', '1E'])
    @patch('forum.services.schedule_services._is_more_than_week_away', return_value=False)
    def test_calendar_failure_does_not_save_fallback_times(self, _week, _sheet, calendar, model):
        model.objects.filter.return_value.first.return_value = None

        result = get_block_order_for_day('2026-10-05')

        self.assertEqual(result['times'][0], '8:20-9:30')
        calendar.assert_called_once()
        model.objects.get_or_create.assert_not_called()

    @patch('forum.services.schedule_services.DailySchedule')
    @patch('forum.services.schedule_services.get_calendar_events_for_day', return_value=[])
    @patch('forum.services.schedule_services.get_sheet_row_data', return_value=['', '', '', '', '1A', '1B', '1C', '1D', '1E'])
    @patch('forum.services.schedule_services._is_more_than_week_away', return_value=False)
    def test_unverified_cached_schedule_refreshes(self, _week, _sheet, calendar, model):
        cached = Mock(is_school=True, calendar_verified=False, block_1='1A', block_1_time='old time')
        model.objects.filter.return_value.first.return_value = cached
        model.objects.get_or_create.return_value = cached, False

        result = get_block_order_for_day('2026-10-05')

        self.assertEqual(result['times'][0], '8:20-9:30')
        self.assertTrue(cached.calendar_verified)
        cached.save.assert_called_once_with()
        calendar.assert_called_once()

    @patch('forum.views.feed_views.render')
    @patch('forum.views.feed_views.get_random_greeting', return_value='Hello')
    @patch('forum.views.feed_views.get_all_posts')
    @patch('forum.views.feed_views.datetime')
    def test_home_uses_vancouver_date_after_november_time_change(self, view_datetime, posts, _greeting, render):
        from forum.views.feed_views import for_you

        view_datetime.now.return_value = datetime.datetime(
            2026, 11, 1, 0, 30, tzinfo=ZoneInfo('America/Vancouver')
        )
        posts.return_value.object_list = []
        request = Mock()
        request.user.is_authenticated = True
        request.GET = {}

        for_you(request)

        view_datetime.now.assert_called_once_with(ZoneInfo('America/Vancouver'))
        context = render.call_args.args[2]
        self.assertEqual(context['today_iso'], '2026-11-01')
        self.assertEqual(context['tomorrow_iso'], '2026-11-02')
