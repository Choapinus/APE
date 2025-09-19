---
name: resource_explanation
description: Explains how to use a resource
arguments:
  - name: resources
    description: A list of resources
    required: true
---
{% for resource in resources %}
- **{{ resource.name }}**: {{ resource.description }}
  - URI: `{{ resource.uri }}`
{% if resource.parameters.properties %}
  - Parameters:
{% for param, details in resource.parameters.properties.items() %}
    - `{{ param }}` ({{ details.type }}): {{ details.description }}
{% endfor %}
{% endif %}
{% endfor %}
