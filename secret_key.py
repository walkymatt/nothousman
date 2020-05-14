#!/usr/bin/env python
from django.core.management.utils import get_random_secret_key
with open('secret_key.txt', 'w') as f:
    print(get_random_secret_key(), file=f)