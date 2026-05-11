from django.utils.text import slugify


def generate_unique_slug(model_class, value, slug_field="slug"):
    """
    Generate a unique slug for a model instance.
    Appends -2, -3, etc. if the slug already exists.
    """
    base_slug = slugify(value)
    slug = base_slug
    counter = 2
    while model_class.objects.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug
