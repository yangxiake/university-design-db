"""Read YAML safely, using LibYAML when available (never a general loader)."""
import yaml

SAFE_LOADER = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)


def load_yaml(text):
    return yaml.load(text, Loader=SAFE_LOADER)
