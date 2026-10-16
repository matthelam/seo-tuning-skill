# Security

Please report a vulnerability privately through this repository's **Security** tab
("Report a vulnerability"), not in a public issue.

The skill handles one secret: the `SEO_JEV_API_KEY` for your seo-jev-analyzer deployment. It is
read from the environment, sent only in the Authorization header to `SEO_JEV_MCP_URL`, and removed
from any error text. It is never written to the workspace. If you think a key has leaked, rotate
it in your deployment's `MCP_API_KEY` setting.
