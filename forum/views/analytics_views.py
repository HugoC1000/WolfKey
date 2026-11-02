import csv
import io
from datetime import timedelta

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from forum.models import AnalyticsCoverage
from forum.services.analytics_service import METRICS, VANCOUVER, daily_rows


class ExportForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    metrics = forms.MultipleChoiceField(choices=list(METRICS.items()), widget=forms.CheckboxSelectMultiple)

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end'):
            if data['start'] > data['end']:
                raise forms.ValidationError('Start date must be on or before end date.')
            if data['end'] > timezone.localtime(timezone.now(), VANCOUVER).date():
                raise forms.ValidationError('End date cannot be in the future.')
        return data


@require_GET
def analytics_export(request, download=False):
    if not request.user.has_perm('forum.export_analytics'):
        raise PermissionDenied
    today = timezone.localtime(timezone.now(), VANCOUVER).date()
    initial = {'start': today - timedelta(days=29), 'end': today, 'metrics': list(METRICS)}
    form = ExportForm(request.GET if request.GET or download else None, initial=initial)
    coverage = AnalyticsCoverage.objects.filter(pk=1).values_list('started_at', flat=True).first()
    if download and form.is_valid():
        # Canonical order, regardless of checkbox submission order.
        selected = [key for key in METRICS if key in form.cleaned_data['metrics']]
        start, end = form.cleaned_data['start'], form.cleaned_data['end']
        output = io.StringIO(newline='')
        output.write('\ufeff')
        writer = csv.writer(output)
        writer.writerow(['date', *selected])
        writer.writerows(daily_rows(start, end, selected, coverage))
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="wolfkey-analytics-{start}-{end}.csv"'
        response['Cache-Control'] = 'no-store'
        return response
    return TemplateResponse(request, 'admin/analytics_export.html', {
        **admin.site.each_context(request), 'title': 'Daily analytics export',
        'form': form, 'coverage': timezone.localtime(coverage, VANCOUVER) if coverage else None,
    }, status=400 if download else 200)
