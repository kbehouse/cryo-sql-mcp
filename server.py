from mcp.server.fastmcp import FastMCP
import os
import requests
import subprocess
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
import argparse
import sys

# Create an MCP server
mcp = FastMCP("cryo-query-mcp")


# Get the default RPC URL from environment or use fallback
DEFAULT_RPC_URL = "https://mainnet.base.org"
# Default data directory for storing output
DEFAULT_DATA_DIR = str(Path.home() / ".cryo-mcp" / "data")

DEFAULT_CRYO_PATH = 'cryo'


@mcp.tool()
def get_latest_block_number() -> Optional[int]:
    """Get the latest block number from the Ethereum node"""
    rpc_url = os.environ.get("ETH_RPC_URL", DEFAULT_RPC_URL)

    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }

    try:
        response = requests.post(rpc_url, json=payload)
        response_data = response.json()

        if 'result' in response_data:
            # Convert hex to int
            latest_block = int(response_data['result'], 16)
            print(f"Latest block number: {latest_block}")
            return latest_block
        else:
            print(
                f"Error fetching latest block: {response_data.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"Exception when fetching latest block: {e}")
        return None


@mcp.tool()
def list_datasets() -> List[str]:
    """Return a list of all available cryo datasets"""
    # Ensure we have the RPC URL
    rpc_url = os.environ.get("ETH_RPC_URL", DEFAULT_RPC_URL)
    # cryo exe path
    cryo_path = os.environ.get("CRYO_PATH", DEFAULT_CRYO_PATH)
    result = subprocess.run(
        [cryo_path, "help", "datasets", "-r", rpc_url],
        capture_output=True,
        text=True
    )

    # Parse the output to extract dataset names
    lines = result.stdout.split('\n')
    datasets = []

    for line in lines:
        if line.startswith('- ') and not line.startswith('- blocks_and_transactions:'):
            # Extract dataset name, removing any aliases
            dataset = line[2:].split(' (alias')[0].strip()
            datasets.append(dataset)
        if line == 'dataset group names':
            break

    return datasets


@mcp.tool()
def list_dataset_schema(dataset: str) -> List[str]:
    """Return a list of all available cryo specific dataset fields"""
    # cryo exe path
    cryo_path = os.environ.get("CRYO_PATH", DEFAULT_CRYO_PATH)
    result = subprocess.run(
        [cryo_path, "help", dataset],
        capture_output=True,
        text=True
    )

    # Parse the output to extract schema fields
    lines = result.stdout.split('\n')
    schema_fields = []
    capture_fields = False

    for line in lines:
        if line.startswith('schema for'):
            capture_fields = True
            continue
        elif line.startswith('sorting') or line.startswith('other'):
            capture_fields = False
            continue
            
        if capture_fields and line.startswith('- '):
            # Extract just the field name before the colon
            field = line[2:].split(':')[0].strip()
            schema_fields.append(field)

    return schema_fields


@mcp.tool()
def download_dataset(
    dataset: str,
    blocks: Optional[str] = None,
    start_block: int = None,
    end_block: int = None,
    contract: Optional[str] = None,
    output_format: str = "csv",
    sql_query: str = None
) -> Dict[str, Any]:
    """Download a cryo dataset, optionally with a SQL query to filter the data"""
    # Ensure we have the RPC URL
    rpc_url = os.environ.get("ETH_RPC_URL", DEFAULT_RPC_URL)
    # cryo exe path
    cryo_path = os.environ.get("CRYO_PATH", DEFAULT_CRYO_PATH)
    # Build the cryo command
    cmd = [cryo_path, dataset, "-r", rpc_url]

    # Handle block range (priority: blocks > use_latest > start/end_block > default)
    if blocks:
        # Use specified block range string directly
        cmd.extend(["-b", blocks])
    elif start_block is not None:
        # Convert integer block numbers to string range
        if end_block is not None:
            # Note: cryo uses [start:end) range (inclusive start, exclusive end)
            # Add 1 to end_block to include it in the range
            block_range = f"{start_block}:{end_block+1}"
        else:
            # If only start_block is provided, get 10 blocks starting from there
            block_range = f"{start_block}:{start_block+10}"

        print(f"Using block range: {block_range}")
        cmd.extend(["-b", block_range])
    else:
        # Default to a reasonable block range if none specified
        cmd.extend(["-b", "1000:1010"])

    # Handle dataset-specific address parameters
    # For all address-based filters, we use the contract parameter
    # but map it to the correct flag based on the dataset
    if contract:
        # Check if this is a dataset that requires a different parameter name
        if dataset == 'balances':
            # For balances dataset, contract parameter maps to --address
            cmd.extend(["--address", contract])
        else:
            # For other datasets like logs, transactions, etc. use --contract
            cmd.extend(["--contract", contract])

    if output_format == "json":
        cmd.append("--json")
    elif output_format == "csv":
        cmd.append("--csv")

    if sql_query:
        cmd.append("--sql-query")
        cmd.append(sql_query)

    # Get the base data directory
    data_dir = Path(os.environ.get("CRYO_DATA_DIR", DEFAULT_DATA_DIR))

    output_dir = data_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd.extend(["-o", str(output_dir)])

    # Print the command for debugging
    print(f"Running query command: {' '.join(cmd)}")

    # Execute the command
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "error": result.stderr,
            "stdout": result.stdout,
            "command": " ".join(cmd)
        }

    # Try to find the report file which contains info about generated files
    report_dir = output_dir / ".cryo" / "reports"
    if report_dir.exists():
        # Get the most recent report file (should be the one we just created)
        report_files = sorted(report_dir.glob("*.json"),
                              key=lambda x: x.stat().st_mtime, reverse=True)
        if report_files:
            with open(report_files[0], 'r') as f:
                report_data = json.load(f)
                # Get the list of completed files from the report
                if "results" in report_data and "completed_paths" in report_data["results"]:
                    completed_files = report_data["results"]["completed_paths"]
                    print(
                        f"Found {len(completed_files)} files in Cryo report: {completed_files}")

                    # Return the list of files and their count
                    return {
                        "files": completed_files,
                        "count": len(completed_files),
                        "format": output_format
                    }

    # Fallback to glob search if report file not found or doesn't contain the expected data
    output_files = list(output_dir.glob(f"*{dataset}*.{output_format}"))
    print(f"Output files found via glob: {output_files}")

    if not output_files:
        return {"error": "No output files generated", "command": " ".join(cmd)}

    # Convert Path objects to strings for JSON serialization
    file_paths = [str(file_path) for file_path in output_files]

    return {
        "files": file_paths,
        "count": len(file_paths),
        "format": output_format
    }


def parse_args(args=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Cryo Data Server")
    parser.add_argument(
        "--rpc-url",
        type=str,
        help="Ethereum RPC URL to use for requests"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Directory to store downloaded data, defaults to ~/.cryo-mcp/data/"
    )
    parser.add_argument(
        "--cryo-path",
        type=str,
        help="Cryo Exe path"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information and exit"
    )

    return parser.parse_args(args)


def main():
    """Main entry point for the command-line script"""
    args = parse_args()

    # Set RPC URL with priority: command line > environment variable > default
    if args.rpc_url:
        rpc_url = args.rpc_url
        os.environ["ETH_RPC_URL"] = rpc_url
        print(f"Using RPC URL from command line: {rpc_url}")
    elif os.environ.get("ETH_RPC_URL"):
        rpc_url = os.environ["ETH_RPC_URL"]
        print(f"Using RPC URL from environment: {rpc_url}")
    else:
        rpc_url = DEFAULT_RPC_URL
        os.environ["ETH_RPC_URL"] = rpc_url
        print(f"Using default RPC URL: {rpc_url}")

    # Set data directory with priority: command line > environment variable > default
    if args.data_dir:
        data_dir = args.data_dir
        os.environ["CRYO_DATA_DIR"] = data_dir
        print(f"Using data directory from command line: {data_dir}")
    elif os.environ.get("CRYO_DATA_DIR"):
        data_dir = os.environ["CRYO_DATA_DIR"]
        print(f"Using data directory from environment: {data_dir}")
    else:
        data_dir = DEFAULT_DATA_DIR
        os.environ["CRYO_DATA_DIR"] = data_dir
        print(f"Using default data directory: {data_dir}")

    # Set cryo path with priority: command line > environment variable > default
    if args.cryo_path:
        cryo_path = args.cryo_path
        os.environ["CRYO_PATH"] = cryo_path
        print(f"Using cryo path from command line: {cryo_path}")
    elif os.environ.get("CRYO_PATH"):
        cryo_path = os.environ["CRYO_PATH"]
        print(f"Using cryo path from environment: {cryo_path}")
    else:
        cryo_path = DEFAULT_CRYO_PATH
        os.environ["CRYO_PATH"] = cryo_path
        print(f"Using default cryo path: {cryo_path}")

    # Ensure data directory exists
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    mcp.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
