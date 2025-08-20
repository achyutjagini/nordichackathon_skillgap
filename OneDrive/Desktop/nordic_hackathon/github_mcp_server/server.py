#!/usr/bin/env python3
"""
GitHub MCP Server - Fetches repository metadata, README files, and code structure
"""

import asyncio
import json
import os
import logging
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import requests
from github import Github, GithubException
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from pydantic import AnyUrl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-mcp-server")

class GitHubMCPServer:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_client = None
        if self.github_token:
            self.github_client = Github(self.github_token)
        
        self.server = Server("github-mcp-server")
        self.setup_handlers()

    def setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available GitHub resources"""
            return [
                Resource(
                    uri=AnyUrl("github://repository/metadata"),
                    name="Repository Metadata",
                    description="Get metadata for a GitHub repository",
                    mimeType="application/json"
                ),
                Resource(
                    uri=AnyUrl("github://repository/readme"),
                    name="Repository README",
                    description="Get README content for a GitHub repository",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri=AnyUrl("github://repository/structure"),
                    name="Repository Structure",
                    description="Get file structure of a GitHub repository",
                    mimeType="application/json"
                )
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: AnyUrl) -> str:
            """Read a specific GitHub resource"""
            uri_str = str(uri)
            
            if uri_str.startswith("github://repository/"):
                # Extract repository info from URI
                # Expected format: github://repository/{action}?owner=owner&repo=repo
                parts = uri_str.split("?")
                if len(parts) != 2:
                    raise ValueError("Invalid URI format. Expected: github://repository/{action}?owner=owner&repo=repo")
                
                action = parts[0].split("/")[-1]
                params = dict(param.split("=") for param in parts[1].split("&"))
                
                owner = params.get("owner")
                repo = params.get("repo")
                
                if not owner or not repo:
                    raise ValueError("Missing owner or repo parameter")
                
                if action == "metadata":
                    return await self.get_repository_metadata(owner, repo)
                elif action == "readme":
                    return await self.get_repository_readme(owner, repo)
                elif action == "structure":
                    return await self.get_repository_structure(owner, repo)
                else:
                    raise ValueError(f"Unknown action: {action}")
            
            raise ValueError(f"Unknown resource URI: {uri}")

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available GitHub tools"""
            return [
                Tool(
                    name="get_repo_info",
                    description="Get comprehensive information about a GitHub repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "GitHub repository URL (e.g., https://github.com/owner/repo)"
                            }
                        },
                        "required": ["repo_url"]
                    }
                ),
                Tool(
                    name="get_repo_structure",
                    description="Get the file structure of a GitHub repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "GitHub repository URL"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum depth to traverse (default: 3)",
                                "default": 3
                            }
                        },
                        "required": ["repo_url"]
                    }
                ),
                Tool(
                    name="get_repo_readme",
                    description="Get the README content of a GitHub repository",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "GitHub repository URL"
                            }
                        },
                        "required": ["repo_url"]
                    }
                ),
                Tool(
                    name="analyze_repo_dependencies",
                    description="Analyze repository dependencies from package files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "GitHub repository URL"
                            }
                        },
                        "required": ["repo_url"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "get_repo_info":
                    result = await self.get_repo_info(arguments["repo_url"])
                elif name == "get_repo_structure":
                    max_depth = arguments.get("max_depth", 3)
                    result = await self.get_repo_structure_tool(arguments["repo_url"], max_depth)
                elif name == "get_repo_readme":
                    result = await self.get_repo_readme_tool(arguments["repo_url"])
                elif name == "analyze_repo_dependencies":
                    result = await self.analyze_repo_dependencies(arguments["repo_url"])
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [TextContent(type="text", text=result)]
            
            except Exception as e:
                logger.error(f"Error in tool {name}: {str(e)}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    def parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo name"""
        parsed = urlparse(repo_url)
        if parsed.netloc != "github.com":
            raise ValueError("Invalid GitHub URL")
        
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub repository URL format")
        
        return path_parts[0], path_parts[1]

    async def get_repository_metadata(self, owner: str, repo: str) -> str:
        """Get repository metadata"""
        try:
            if self.github_client:
                repo_obj = self.github_client.get_repo(f"{owner}/{repo}")
                metadata = {
                    "name": repo_obj.name,
                    "full_name": repo_obj.full_name,
                    "description": repo_obj.description,
                    "language": repo_obj.language,
                    "stars": repo_obj.stargazers_count,
                    "forks": repo_obj.forks_count,
                    "open_issues": repo_obj.open_issues_count,
                    "created_at": repo_obj.created_at.isoformat(),
                    "updated_at": repo_obj.updated_at.isoformat(),
                    "size": repo_obj.size,
                    "default_branch": repo_obj.default_branch,
                    "topics": repo_obj.get_topics(),
                    "license": repo_obj.license.name if repo_obj.license else None,
                    "homepage": repo_obj.homepage,
                    "clone_url": repo_obj.clone_url,
                    "ssh_url": repo_obj.ssh_url
                }
            else:
                # Fallback to GitHub API without authentication
                url = f"https://api.github.com/repos/{owner}/{repo}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                metadata = {
                    "name": data["name"],
                    "full_name": data["full_name"],
                    "description": data["description"],
                    "language": data["language"],
                    "stars": data["stargazers_count"],
                    "forks": data["forks_count"],
                    "open_issues": data["open_issues_count"],
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"],
                    "size": data["size"],
                    "default_branch": data["default_branch"],
                    "topics": data.get("topics", []),
                    "license": data["license"]["name"] if data.get("license") else None,
                    "homepage": data["homepage"],
                    "clone_url": data["clone_url"],
                    "ssh_url": data["ssh_url"]
                }
            
            return json.dumps(metadata, indent=2)
        
        except Exception as e:
            logger.error(f"Error getting repository metadata: {str(e)}")
            raise

    async def get_repository_readme(self, owner: str, repo: str) -> str:
        """Get repository README content"""
        try:
            if self.github_client:
                repo_obj = self.github_client.get_repo(f"{owner}/{repo}")
                readme = repo_obj.get_readme()
                return readme.decoded_content.decode('utf-8')
            else:
                # Fallback to GitHub API without authentication
                url = f"https://api.github.com/repos/{owner}/{repo}/readme"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                import base64
                content = base64.b64decode(data["content"]).decode('utf-8')
                return content
        
        except Exception as e:
            logger.error(f"Error getting repository README: {str(e)}")
            raise

    async def get_repository_structure(self, owner: str, repo: str, max_depth: int = 3) -> str:
        """Get repository file structure"""
        try:
            if self.github_client:
                repo_obj = self.github_client.get_repo(f"{owner}/{repo}")
                contents = repo_obj.get_contents("")
                structure = await self._build_structure_tree(contents, repo_obj, max_depth, 0)
            else:
                # Fallback to GitHub API without authentication
                url = f"https://api.github.com/repos/{owner}/{repo}/contents"
                response = requests.get(url)
                response.raise_for_status()
                contents = response.json()
                structure = await self._build_structure_tree_api(contents, owner, repo, max_depth, 0)
            
            return json.dumps(structure, indent=2)
        
        except Exception as e:
            logger.error(f"Error getting repository structure: {str(e)}")
            raise

    async def _build_structure_tree(self, contents, repo_obj, max_depth: int, current_depth: int) -> List[Dict]:
        """Build file structure tree using PyGithub"""
        structure = []
        
        if current_depth >= max_depth:
            return structure
        
        for content in contents:
            item = {
                "name": content.name,
                "type": content.type,
                "path": content.path,
                "size": content.size if content.type == "file" else None
            }
            
            if content.type == "dir" and current_depth < max_depth - 1:
                try:
                    sub_contents = repo_obj.get_contents(content.path)
                    item["children"] = await self._build_structure_tree(
                        sub_contents, repo_obj, max_depth, current_depth + 1
                    )
                except Exception as e:
                    logger.warning(f"Could not access directory {content.path}: {str(e)}")
                    item["children"] = []
            
            structure.append(item)
        
        return structure

    async def _build_structure_tree_api(self, contents, owner: str, repo: str, max_depth: int, current_depth: int) -> List[Dict]:
        """Build file structure tree using direct API calls"""
        structure = []
        
        if current_depth >= max_depth:
            return structure
        
        for content in contents:
            item = {
                "name": content["name"],
                "type": content["type"],
                "path": content["path"],
                "size": content.get("size") if content["type"] == "file" else None
            }
            
            if content["type"] == "dir" and current_depth < max_depth - 1:
                try:
                    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{content['path']}"
                    response = requests.get(url)
                    if response.status_code == 200:
                        sub_contents = response.json()
                        item["children"] = await self._build_structure_tree_api(
                            sub_contents, owner, repo, max_depth, current_depth + 1
                        )
                    else:
                        item["children"] = []
                except Exception as e:
                    logger.warning(f"Could not access directory {content['path']}: {str(e)}")
                    item["children"] = []
            
            structure.append(item)
        
        return structure

    async def get_repo_info(self, repo_url: str) -> str:
        """Get comprehensive repository information"""
        owner, repo = self.parse_github_url(repo_url)
        
        metadata = await self.get_repository_metadata(owner, repo)
        readme = await self.get_repository_readme(owner, repo)
        structure = await self.get_repository_structure(owner, repo)
        
        result = {
            "repository_url": repo_url,
            "metadata": json.loads(metadata),
            "readme_preview": readme[:500] + "..." if len(readme) > 500 else readme,
            "structure_summary": json.loads(structure)[:10]  # First 10 items
        }
        
        return json.dumps(result, indent=2)

    async def get_repo_structure_tool(self, repo_url: str, max_depth: int = 3) -> str:
        """Tool wrapper for getting repository structure"""
        owner, repo = self.parse_github_url(repo_url)
        return await self.get_repository_structure(owner, repo, max_depth)

    async def get_repo_readme_tool(self, repo_url: str) -> str:
        """Tool wrapper for getting repository README"""
        owner, repo = self.parse_github_url(repo_url)
        return await self.get_repository_readme(owner, repo)

    async def analyze_repo_dependencies(self, repo_url: str) -> str:
        """Analyze repository dependencies from package files"""
        owner, repo = self.parse_github_url(repo_url)
        dependencies = {}
        
        # Common dependency files to check
        dependency_files = [
            "package.json",      # Node.js
            "requirements.txt",  # Python
            "Pipfile",          # Python (pipenv)
            "pyproject.toml",   # Python (modern)
            "Gemfile",          # Ruby
            "composer.json",    # PHP
            "pom.xml",          # Java (Maven)
            "build.gradle",     # Java (Gradle)
            "Cargo.toml",       # Rust
            "go.mod"            # Go
        ]
        
        try:
            if self.github_client:
                repo_obj = self.github_client.get_repo(f"{owner}/{repo}")
                
                for file_name in dependency_files:
                    try:
                        file_content = repo_obj.get_contents(file_name)
                        content = file_content.decoded_content.decode('utf-8')
                        dependencies[file_name] = await self._parse_dependency_file(file_name, content)
                    except GithubException:
                        continue  # File doesn't exist
            else:
                # Fallback to API calls
                for file_name in dependency_files:
                    try:
                        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_name}"
                        response = requests.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            import base64
                            content = base64.b64decode(data["content"]).decode('utf-8')
                            dependencies[file_name] = await self._parse_dependency_file(file_name, content)
                    except Exception:
                        continue
            
            return json.dumps(dependencies, indent=2)
        
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {str(e)}")
            raise

    async def _parse_dependency_file(self, file_name: str, content: str) -> Dict:
        """Parse dependency file content"""
        try:
            if file_name == "package.json":
                data = json.loads(content)
                return {
                    "dependencies": data.get("dependencies", {}),
                    "devDependencies": data.get("devDependencies", {}),
                    "scripts": data.get("scripts", {})
                }
            elif file_name == "requirements.txt":
                lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                return {"requirements": lines}
            elif file_name in ["pyproject.toml", "Cargo.toml"]:
                # Basic TOML parsing (would need toml library for full support)
                return {"content": content[:500] + "..." if len(content) > 500 else content}
            else:
                return {"content": content[:500] + "..." if len(content) > 500 else content}
        except Exception as e:
            logger.warning(f"Could not parse {file_name}: {str(e)}")
            return {"error": f"Could not parse {file_name}"}

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="github-mcp-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )

async def main():
    """Main entry point"""
    server = GitHubMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
