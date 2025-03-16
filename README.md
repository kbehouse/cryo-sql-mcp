## Install

1. install uv

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. install cryo sql version

```
git clone --branch sql-query-option https://github.com/kbehouse/cryo/tree/sql-query-option

cd cryo && cargo build --release
```

### Cursor MCP setting

Cursor -> Settings... -> Cursor settings -> MCP

MAC: uv path /User/<user_name>/.local/bin/uv

```
{
  "mcpServers": {
   "cryo": {
      "command": "<uv-path>",
      "args": [
        "--directory",
        "<python-path>",
        "run",
        "<python-path>/server.py",
        "--rpc-url",
        "https://mainnet.base.org",
        "--data-dir",
        "<data-path>",
        "--cryo-path",
        "<cryo-rust-path>/target/release/cryo"
      ]
    }
  }
}
```

## Agent

cusor agent mode: cmd + L -> Agent

prompt example

```
download logs for latest 10 blocks and filter address='0x4200000000000000000000000000000000000006'
```

## Acknowledgement

this project refer from cryo-mcp: https://github.com/z80dev/cryo-mcp/tree/main
