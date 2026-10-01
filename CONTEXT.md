# Scheduled transit

Language for interpreting published schedules and identifying their occurrences.

## Language

**Service date**:
The operating day assigned to a scheduled trip. A call after midnight can belong to the preceding service date.
_Avoid_: Boarding date, trip-ID suffix date

**Trip occurrence**:
A particular scheduled trip on its service date, retaining the complete source trip identity and occurrence start time.
_Avoid_: Normalized trip key

**Stop call**:
One ordered visit to a stop within a trip occurrence. Revisiting the same stop creates another call even when its displayed time is identical.
_Avoid_: Unique trip-stop pair

**Raw service clock**:
A published arrival or departure time measured within its originating service day, including values beyond 24:00.
_Avoid_: Observed time, live time

**Effective service clock**:
The interpreted schedule time used for a stop call by the routing engine. Its precision and interpretation remain attributable to the raw service clock.
_Avoid_: Corrected source time, predicted time
