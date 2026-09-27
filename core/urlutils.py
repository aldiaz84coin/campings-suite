from django.urls import reverse


def camping_reverse(request, name, camping, **kwargs):
    """Reverse a public camping URL for the platform or a custom domain.

    On a camping's own domain the URLs carry no slug (the domain identifies
    the camping), so the same template can serve both cases.
    """
    if request is not None and getattr(request, "domain_camping_id", None):
        return reverse(name, kwargs=kwargs or None)
    return reverse(name, kwargs={"slug": camping.slug, **kwargs})
