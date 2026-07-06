"""
BizYangu — reports serializers.

These aren't model serializers — the reports app has no models (see
models.py). They're query-param validators for the report endpoints in
views.py: DateQuerySerializer for single-date endpoints (?date=), and
PeriodQuerySerializer for range endpoints (?start=&end=). Keeping the
validation here rather than inline in each view means every report
endpoint rejects bad input the same way, with the same error shape.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.core.messages import MESSAGES

# Period endpoints (period/, products/, losses/) default to the last 30
# days when no start/end is given, and refuse windows longer than this —
# a duka owner asking for "all time" would otherwise silently hammer the
# DB with an unbounded aggregate query.
MAX_PERIOD_DAYS = 366


class DateQuerySerializer(serializers.Serializer):
    """Validates the optional ?date= query param used by /daily/ and /eod-summary/."""

    date = serializers.DateField(
        required=False,
        error_messages={'invalid': MESSAGES['INVALID_DATE_FORMAT']},
    )

    def get_date(self):
        """Returns the validated date, defaulting to today (business-local)."""
        return self.validated_data.get('date') or timezone.localdate()


class PeriodQuerySerializer(serializers.Serializer):
    """
    Validates the optional ?start=&end= query params used by /period/,
    /products/, and /losses/. Defaults to the last 30 days (inclusive)
    when neither is given.
    """

    start = serializers.DateField(
        required=False,
        error_messages={'invalid': MESSAGES['INVALID_DATE_FORMAT']},
    )
    end = serializers.DateField(
        required=False,
        error_messages={'invalid': MESSAGES['INVALID_DATE_FORMAT']},
    )

    def validate(self, attrs):
        today = timezone.localdate()
        start = attrs.get('start') or (today - timedelta(days=29))
        end = attrs.get('end') or today

        if start > end:
            raise serializers.ValidationError(MESSAGES['INVALID_DATE_RANGE'])

        if (end - start).days > MAX_PERIOD_DAYS:
            raise serializers.ValidationError(
                MESSAGES['DATE_RANGE_TOO_LARGE'].format(max_days=MAX_PERIOD_DAYS)
            )

        attrs['start'] = start
        attrs['end'] = end
        return attrs
