---
name: error_report
description: Formats an error envelope into a user-facing report
arguments:
  - name: tool
    description: Tool name that produced the error
    required: false
  - name: error
    description: Short error message
    required: true
  - name: details
    description: Optional extended error information / traceback
    required: false
---
❌ **An error occurred while executing{{ " tool " + tool if tool else "" }}:**

> {{ error }}

{% if details %}
<details>
<summary>Additional details</summary>

```
{{ details }}
```
</details>
{% endif %}

Please review the input parameters and try again. If the problem persists, contact support. 