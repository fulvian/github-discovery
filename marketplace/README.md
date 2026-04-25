# Marketplace Assets

This directory contains the packaging assets for submitting GitHub Discovery to the [Kilo Marketplace](https://github.com/Kilo-Org/kilo-marketplace).

## What's Here

```
marketplace/
├── mcps/
│   └── github-discovery/
│       └── MCP.yaml          # Marketplace entry definition
└── README.md                 # This file
```

### MCP.yaml

The `MCP.yaml` file defines the GitHub Discovery MCP server entry for the Kilo Marketplace. It specifies:

- **Metadata**: id, name, description, author, URL, tags
- **Prerequisites**: Python 3.12+, GitHub PAT
- **Content**: Three installation methods (UVX, Docker, Remote Server)
- **Parameters**: GitHub Personal Access Token configuration

## Submission Process

To submit GitHub Discovery to the Kilo Marketplace:

### 1. Fork the marketplace repository

```bash
# Fork https://github.com/Kilo-Org/kilo-marketplace to your account
gh repo fork Kilo-Org/kilo-marketplace --clone=false
```

### 2. Create a branch

```bash
git clone https://github.com/YOUR_USERNAME/kilo-marketplace.git
cd kilo-marketplace
git checkout -b add-github-discovery
```

### 3. Copy the MCP.yaml into place

```bash
mkdir -p mcps/github-discovery
cp /path/to/github-discovery/marketplace/mcps/github-discovery/MCP.yaml mcps/github-discovery/MCP.yaml
```

### 4. Validate

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('mcps/github-discovery/MCP.yaml'))"

# Validate against marketplace schema (if available)
npx tsx bin/validate.ts mcps/github-discovery/MCP.yaml
```

### 5. Commit and push

```bash
git add mcps/github-discovery/MCP.yaml
git commit -m "Add GitHub Discovery MCP server"
git push origin add-github-discovery
```

### 6. Open a Pull Request

Open a PR against `Kilo-Org/kilo-marketplace` main branch with:

- **Title**: "Add GitHub Discovery MCP server"
- **Description**: Include what the server does, the real-world use case, and how to test it.

## Verification Checklist

Before submitting, verify:

- [ ] `id` is unique (no existing `github-discovery` in the marketplace)
- [ ] `url` points to the correct repository
- [ ] `author` matches your GitHub username
- [ ] `tags` are relevant and use kebab-case
- [ ] JSON in `content` blocks is valid
- [ ] Parameter placeholders use the `{{KEY}}` template syntax
- [ ] YAML passes syntax validation

## References

- [Kilo Marketplace Repository](https://github.com/Kilo-Org/kilo-marketplace)
- [Contributing Guide](https://github.com/Kilo-Org/kilo-marketplace/blob/main/CONTRIBUTING.md)
- [Existing MCP Entries](https://github.com/Kilo-Org/kilo-marketplace/tree/main/mcps)
