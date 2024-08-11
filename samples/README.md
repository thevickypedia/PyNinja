## Sample Environment Variables

Environment variables can be sourced using any `plaintext` / `JSON` / `YAML` file.
The filepath should be provided as an argument during object instantiation.

⚠️ Sample values are randomly generated strings from https://pinetools.com/random-string-generator

> By default, `PyNinja` will look for a `.env` file in the current working directory.

### Examples

- PlainText: [.env]
- JSON: [secrets.json]
- YAML: [secrets.yaml]

[.env]: .env
[secrets.json]: secrets.json
[secrets.yaml]: secrets.yaml

### Usage

- **CLI**
```shell
pyninja --env "/path/to/env/file" start
```

- **IDE**
```python
import pyninja
pyninja.start(env_file='/path/to/env/file')
```
