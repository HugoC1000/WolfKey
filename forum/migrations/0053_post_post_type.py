# Generated migration to add post_type field to Post model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0052_migrate_posts_to_standardpost'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='''
                        ALTER TABLE forum_post ADD COLUMN IF NOT EXISTS post_type varchar(20);
                        ALTER TABLE forum_post ALTER COLUMN post_type SET DEFAULT 'standard';

                        UPDATE forum_post p
                        SET post_type = 'poll'
                        WHERE EXISTS (
                            SELECT 1 FROM forum_poll fp WHERE fp.post_ptr_id = p.id
                        );

                        UPDATE forum_post p
                        SET post_type = 'standard'
                        WHERE NOT EXISTS (
                            SELECT 1 FROM forum_poll fp WHERE fp.post_ptr_id = p.id
                        );

                        ALTER TABLE forum_post ALTER COLUMN post_type SET NOT NULL;
                    ''',
                    reverse_sql='''
                        ALTER TABLE forum_post DROP COLUMN IF EXISTS post_type;
                    '''
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='post',
                    name='post_type',
                    field=models.CharField(
                        choices=[('standard', 'Standard Post'), ('poll', 'Poll')],
                        default='standard',
                        max_length=20
                    ),
                ),
            ]
        ),
    ]
