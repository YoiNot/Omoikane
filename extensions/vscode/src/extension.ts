import * as vscode from "vscode";

// ── API types ────────────────────────────────────────────────────────

interface Memory {
  id: string;
  project_id: string;
  type: string;
  title: string;
  content: string;
  summary: string | null;
  source_type: string | null;
  source_url: string | null;
  source_author: string | null;
  created_at: string;
  updated_at: string;
}

interface SearchResult {
  memory: Memory;
  score: number;
  chunk_text: string;
}

interface ADR {
  id: string;
  memory_id: string;
  project_id: string;
  title: string;
  context: string;
  decision: string;
  consequences: string;
  alternatives: string[];
  status: string;
  participants: string[];
  decided_at: string | null;
}

// ── API helpers ──────────────────────────────────────────────────────

function getConfig() {
  const config = vscode.workspace.getConfiguration("omoikane");
  return {
    apiUrl: config.get<string>("apiUrl", "http://localhost:8420"),
    projectId: config.get<string>("projectId", ""),
    autoContext: config.get<boolean>("autoContext", false),
  };
}

async function api<T = unknown>(
  path: string,
  method: string,
  body?: unknown
): Promise<T> {
  const { apiUrl } = getConfig();
  const response = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}${text ? ": " + text : ""}`);
  }
  return response.json() as Promise<T>;
}

function requireProject(): string {
  const { projectId } = getConfig();
  if (!projectId) {
    throw new Error("Set omoikane.projectId in VS Code settings (Cmd+, → Omoikane)");
  }
  return projectId;
}

// ── Tree data providers ──────────────────────────────────────────────

type TreeItem = vscode.TreeItem & { data?: Memory | ADR; children?: TreeItem[] };

class MemoryTreeProvider implements vscode.TreeDataProvider<TreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<TreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
  private items: Memory[] = [];

  refresh(): void {
    this.load().then(() => this._onDidChangeTreeData.fire(undefined));
  }

  private async load() {
    try {
      const projectId = requireProject();
      this.items = await api<Memory[]>(
        `/v1/projects/${projectId}/memories`,
        "GET"
      );
    } catch {
      this.items = [];
    }
  }

  getTreeItem(element: TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: TreeItem): Promise<TreeItem[]> {
    if (element) return element.children || [];
    await this.load();

    if (this.items.length === 0) {
      const empty = new vscode.TreeItem("No memories yet");
      empty.iconPath = new vscode.ThemeIcon("info");
      return [empty];
    }

    const byType = new Map<string, Memory[]>();
    for (const m of this.items) {
      const arr = byType.get(m.type) || [];
      arr.push(m);
      byType.set(m.type, arr);
    }

    const groups: TreeItem[] = [];
    for (const [type, memories] of byType) {
      const group: TreeItem = Object.assign(
        new vscode.TreeItem(
          `${type} (${memories.length})`,
          vscode.TreeItemCollapsibleState.Expanded
        ),
        { children: memories.map((m) => memoryToItem(m)) }
      );
      group.iconPath = new vscode.ThemeIcon(typeIcon(type));
      groups.push(group);
    }
    return groups;
  }
}

class ADRTreeProvider implements vscode.TreeDataProvider<TreeItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<TreeItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
  private items: ADR[] = [];

  refresh(): void {
    this.load().then(() => this._onDidChangeTreeData.fire(undefined));
  }

  private async load() {
    try {
      const projectId = requireProject();
      this.items = await api<ADR[]>(
        `/v1/decisions/${projectId}`,
        "GET"
      );
    } catch {
      this.items = [];
    }
  }

  getTreeItem(element: TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: TreeItem): Promise<TreeItem[]> {
    if (element) return [];
    await this.load();

    if (this.items.length === 0) {
      const empty = new vscode.TreeItem("No ADRs yet");
      empty.iconPath = new vscode.ThemeIcon("info");
      return [empty];
    }

    return this.items.map((a) => {
      const item = new vscode.TreeItem(
        a.title,
        vscode.TreeItemCollapsibleState.None
      );
      item.description = a.status;
      item.iconPath = new vscode.ThemeIcon(
        a.status === "accepted"
          ? "check"
          : a.status === "superseded"
            ? "replace"
            : "circle-outline"
      );
      item.command = {
        command: "omoikane.viewMemory",
        title: "View",
        arguments: [a],
      };
      return item;
    });
  }
}

// ── Helpers ──────────────────────────────────────────────────────────

function typeIcon(type: string): string {
  const icons: Record<string, string> = {
    decision: "git-commit",
    pattern: "symbol-misc",
    constraint: "warning",
    context: "file-text",
    discussion: "comment-discussion",
  };
  return icons[type] || "note";
}

function memoryToItem(m: Memory): TreeItem {
  const item = new vscode.TreeItem(
    m.title,
    vscode.TreeItemCollapsibleState.None
  );
  item.description = m.source_type || m.type;
  item.iconPath = new vscode.ThemeIcon(typeIcon(m.type));
  item.command = {
    command: "omoikane.viewMemory",
    title: "View",
    arguments: [m],
  };
  return item;
}

function showMemoryPanel(title: string, content: string) {
  const panel = vscode.window.createWebviewPanel(
    "omoikaneMemory",
    title,
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );
  panel.webview.html = `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family); padding: 16px; line-height: 1.6; color: var(--vscode-foreground); }
  pre { background: var(--vscode-textCodeBlock-background); padding: 12px; border-radius: 4px; overflow-x: auto; }
  code { font-family: var(--vscode-editor-font-family); }
  h1, h2, h3 { color: var(--vscode-titleBar-activeForeground); }
  a { color: var(--vscode-textLink-foreground); }
</style>
</head>
<body>${markdownToHtml(content)}</body>
</html>`;
}

function markdownToHtml(md: string): string {
  return md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

// ── Status bar ───────────────────────────────────────────────────────

let statusBarItem: vscode.StatusBarItem;

function updateStatusBar(connected: boolean, projectName?: string) {
  if (!statusBarItem) return;
  if (connected) {
    statusBarItem.text = `$(brain) Omoikane${projectName ? ": " + projectName : ""}`;
    statusBarItem.tooltip = "Omoikane connected";
    statusBarItem.backgroundColor = undefined;
  } else {
    statusBarItem.text = "$(brain) Omoikane: offline";
    statusBarItem.tooltip = "Cannot reach Omoikane API";
    statusBarItem.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.warningBackground"
    );
  }
}

async function checkConnection(): Promise<boolean> {
  try {
    const { apiUrl } = getConfig();
    const resp = await fetch(`${apiUrl}/v1/projects/test`, {
      method: "GET",
      signal: AbortSignal.timeout(3000),
    });
    return resp.ok || resp.status === 404;
  } catch {
    return false;
  }
}

// ── Activate ─────────────────────────────────────────────────────────

export async function activate(context: vscode.ExtensionContext) {
  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = "omoikane.configure";
  context.subscriptions.push(statusBarItem);

  // Tree providers
  const memoryTree = new MemoryTreeProvider();
  const adrTree = new ADRTreeProvider();
  vscode.window.registerTreeDataProvider("omoikane.memories", memoryTree);
  vscode.window.registerTreeDataProvider("omoikane.adrs", adrTree);

  // Check connection on startup
  const connected = await checkConnection();
  updateStatusBar(connected);

  // Periodic connection check
  const interval = setInterval(async () => {
    const ok = await checkConnection();
    updateStatusBar(ok);
  }, 30_000);
  context.subscriptions.push({ dispose: () => clearInterval(interval) });

  // ── Commands ─────────────────────────────────────────────────────

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.search", async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search project memories",
        placeHolder: "e.g., how does authentication work",
        validateInput: (v) => (v.trim() ? null : "Query required"),
      });
      if (!query) return;

      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Searching..." },
        async () => {
          try {
            const projectId = requireProject();
            const results = await api<SearchResult[]>("/v1/search", "POST", {
              query,
              project_id: projectId,
              limit: 10,
            });

            if (results.length === 0) {
              vscode.window.showInformationMessage("No results found");
              return;
            }

            const items = results.map((r) => ({
              label: `$(notebook) [${r.memory.type}] ${r.memory.title}`,
              description: `score: ${r.score.toFixed(2)}`,
              detail: r.chunk_text.substring(0, 150),
              result: r,
            }));

            const selected = await vscode.window.showQuickPick(items, {
              placeHolder: `${results.length} results — select to view`,
              matchOnDescription: true,
              matchOnDetail: true,
            });

            if (selected) {
              showMemoryPanel(selected.result.memory.title, selected.result.memory.content);
            }
          } catch (e: unknown) {
            vscode.window.showErrorMessage(`Search failed: ${fmt(e)}`);
          }
        }
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.context", async () => {
      // Use active editor selection or prompt
      const editor = vscode.window.activeTextEditor;
      let task = "";
      if (editor && !editor.selection.isEmpty) {
        task = editor.document.getText(editor.selection);
      }
      if (!task) {
        task =
          (await vscode.window.showInputBox({
            prompt: "Describe what you're working on",
            placeHolder: "e.g., implement rate limiting middleware",
            validateInput: (v) => (v.trim() ? null : "Description required"),
          })) || "";
      }
      if (!task) return;

      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Assembling context..." },
        async () => {
          try {
            const projectId = requireProject();
            const result = await api<{ context_block: string }>(
              "/v1/context",
              "POST",
              { task, project_id: projectId, limit: 5 }
            );
            showMemoryPanel(`Context: ${task}`, result.context_block);
          } catch (e: unknown) {
            vscode.window.showErrorMessage(`Context assembly failed: ${fmt(e)}`);
          }
        }
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.createMemory", async () => {
      const editor = vscode.window.activeTextEditor;
      let content = "";
      if (editor && !editor.selection.isEmpty) {
        content = editor.document.getText(editor.selection);
      }

      const title = await vscode.window.showInputBox({
        prompt: "Memory title",
        validateInput: (v) => (v.trim() ? null : "Title required"),
      });
      if (!title) return;

      const type = await vscode.window.showQuickPick(
        ["decision", "pattern", "constraint", "context", "discussion"],
        { placeHolder: "Memory type" }
      );
      if (!type) return;

      if (!content) {
        content =
          (await vscode.window.showInputBox({
            prompt: "Memory content",
            validateInput: (v) => (v.trim() ? null : "Content required"),
          })) || "";
      }
      if (!content) return;

      try {
        const projectId = requireProject();
        await api("/v1/memories", "POST", {
          project_id: projectId,
          type,
          title,
          content,
        });
        vscode.window.showInformationMessage(`Memory created: ${title}`);
        memoryTree.refresh();
      } catch (e: unknown) {
        vscode.window.showErrorMessage(`Failed: ${fmt(e)}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.createADR", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "ADR title",
        placeHolder: "e.g., Use PostgreSQL for primary database",
        validateInput: (v) => (v.trim() ? null : "Title required"),
      });
      if (!title) return;

      const decision = await vscode.window.showInputBox({
        prompt: "What was decided?",
        validateInput: (v) => (v.trim() ? null : "Decision required"),
      });
      if (!decision) return;

      const contextStr = await vscode.window.showInputBox({
        prompt: "Why was this decision needed?",
      });

      const consequences = await vscode.window.showInputBox({
        prompt: "What are the consequences?",
      });

      try {
        const projectId = requireProject();
        await api("/v1/decisions", "POST", {
          project_id: projectId,
          title,
          decision,
          context: contextStr || "",
          consequences: consequences || "",
          alternatives: [],
          participants: [],
        });
        vscode.window.showInformationMessage(`ADR created: ${title}`);
        adrTree.refresh();
      } catch (e: unknown) {
        vscode.window.showErrorMessage(`Failed: ${fmt(e)}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.listMemories", async () => {
      try {
        const projectId = requireProject();
        const memories = await api<Memory[]>(
          `/v1/projects/${projectId}/memories`,
          "GET"
        );
        if (memories.length === 0) {
          vscode.window.showInformationMessage("No memories yet");
          return;
        }
        const items = memories.map((m) => ({
          label: `$(notebook) [${m.type}] ${m.title}`,
          description: m.source_type || "",
          memory: m,
        }));
        const selected = await vscode.window.showQuickPick(items, {
          placeHolder: `${memories.length} memories`,
        });
        if (selected) {
          showMemoryPanel(selected.memory.title, selected.memory.content);
        }
      } catch (e: unknown) {
        vscode.window.showErrorMessage(`Failed: ${fmt(e)}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.listADRs", async () => {
      try {
        const projectId = requireProject();
        const adrs = await api<ADR[]>(`/v1/decisions/${projectId}`, "GET");
        if (adrs.length === 0) {
          vscode.window.showInformationMessage("No ADRs yet");
          return;
        }
        const items = adrs.map((a) => ({
          label: `$(git-commit) ${a.title}`,
          description: a.status,
          adr: a,
        }));
        const selected = await vscode.window.showQuickPick(items, {
          placeHolder: `${adrs.length} ADRs`,
        });
        if (selected) {
          const content = [
            `## Context\n${selected.adr.context}`,
            `## Decision\n${selected.adr.decision}`,
            `## Consequences\n${selected.adr.consequences}`,
            selected.adr.alternatives.length
              ? `## Alternatives\n${selected.adr.alternatives.join("\n")}`
              : "",
          ]
            .filter(Boolean)
            .join("\n\n");
          showMemoryPanel(selected.adr.title, content);
        }
      } catch (e: unknown) {
        vscode.window.showErrorMessage(`Failed: ${fmt(e)}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.crossSearch", async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search across linked projects",
        placeHolder: "e.g., authentication pattern",
        validateInput: (v) => (v.trim() ? null : "Query required"),
      });
      if (!query) return;

      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Cross-project search..." },
        async () => {
          try {
            const projectId = requireProject();
            const results = await api<SearchResult[]>(
              "/v1/search/cross",
              "POST",
              { query, project_id: projectId, limit: 10 }
            );
            if (results.length === 0) {
              vscode.window.showInformationMessage("No results found across linked projects");
              return;
            }
            const items = results.map((r) => ({
              label: `$(notebook) [${r.memory.type}] ${r.memory.title}`,
              description: `score: ${r.score.toFixed(2)}`,
              detail: r.chunk_text.substring(0, 150),
              result: r,
            }));
            const selected = await vscode.window.showQuickPick(items, {
              placeHolder: `${results.length} results across projects`,
            });
            if (selected) {
              showMemoryPanel(selected.result.memory.title, selected.result.memory.content);
            }
          } catch (e: unknown) {
            vscode.window.showErrorMessage(`Search failed: ${fmt(e)}`);
          }
        }
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.refresh", () => {
      memoryTree.refresh();
      adrTree.refresh();
      checkConnection().then((ok) => updateStatusBar(ok));
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("omoikane.configure", async () => {
      const projectId = await vscode.window.showInputBox({
        prompt: "Project UUID",
        placeHolder: "e.g., 550e8400-e29b-41d4-a716-446655440000",
        value: getConfig().projectId,
      });
      if (projectId !== undefined) {
        await vscode.workspace
          .getConfiguration("omoikane")
          .update("projectId", projectId, vscode.ConfigurationTarget.Workspace);
        vscode.window.showInformationMessage(`Project set: ${projectId}`);
        memoryTree.refresh();
        adrTree.refresh();
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "omoikane.viewMemory",
      (arg: Memory | ADR) => {
        if ("decision" in arg) {
          const a = arg as ADR;
          const content = [
            `## Context\n${a.context}`,
            `## Decision\n${a.decision}`,
            `## Consequences\n${a.consequences}`,
            a.alternatives?.length
              ? `## Alternatives\n${a.alternatives.join("\n")}`
              : "",
          ]
            .filter(Boolean)
            .join("\n\n");
          showMemoryPanel(a.title, content);
        } else {
          const m = arg as Memory;
          showMemoryPanel(m.title, m.content);
        }
      }
    )
  );
}

function fmt(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function deactivate() {}
