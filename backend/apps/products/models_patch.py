"""
PATCH NOTES for apps/products/models.py — apply by hand, not imported.

This file is not a Django app module; it documents the exact edits to
make to the existing models.py so the diff is reviewable before
touching a file with real migration history. Three changes:

1. Add, at the bottom of models.py:

       from .models_external_source import ExternalSource  # noqa: F401

   so `from apps.products.models import ExternalSource` keeps working
   for admin.py/serializers.py without callers needing to know it
   lives in a second file.

2. On GlobalProduct, add a nullable M2M to ExternalSource:

       web_sources = models.ManyToManyField(
           'ExternalSource', blank=True, related_name='candidates',
       )

   Recorded at candidate-creation time (create_web_candidate(), see
   webcrawl.py) so a CANDIDATE created from web search can later be
   traced back to which domain(s) contributed to it — needed for
   ExternalSource.hits_confirmed/hits_disputed bookkeeping once a
   candidate resolves. M2M rather than a single FK because §4.4 of the
   design doc has multiple corroborating domains feeding one
   candidate (case 3.2: an aggregator hit AND a retailer hit both
   contributing to the same Festivita bread candidate).

3. Update the module docstring's "Scope for this pass" paragraph
   (lines 10-15) to remove the now-stale "No external web search /
   Google discovery layer yet" sentence, since this phase adds exactly
   that. Suggested replacement:

       Scope for this pass: internal candidate/consensus loop, plus
       the web-search discovery layer (see webcrawl.py and
       barcode-webcrawl-resolution-scoping.md) that creates CANDIDATEs
       from external evidence when nothing internal exists yet. That
       layer never bypasses this app's own confirm/dispute loop — see
       webcrawl.py's module docstring for the trust-boundary rule.

No changes to GlobalProductVerification — the web-search layer never
writes to it directly (see §4.5 of the design doc).
