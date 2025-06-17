---
name: tool_explanation
description: Explains the purpose and result of a specific tool call in human-readable form
arguments:
  - name: tool_name
    description: Name of the tool that was used
    required: true
  - name: arguments
    description: JSON serialised arguments that were passed
    required: true
  - name: result
    description: Raw result payload returned by the tool
    required: true
---
The tool **{{ tool_name }}** was executed with the following arguments:
```json
{{ arguments }}
```

It returned the result:
```text
{{ result }}
```

Provide a concise summary in *plain English* so the user can easily understand the outcome. 