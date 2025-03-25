import os
import sys

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

# Add backend folder to Python's sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from django.core.management import execute_from_command_line

execute_from_command_line(sys.argv)
