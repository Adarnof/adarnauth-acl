from django.conf import settings

ACL_USER_CHECK_ID_FIELD = getattr(settings, 'ACL_USER_CHECK_ID_FIELD',  'pk')
