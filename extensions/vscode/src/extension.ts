import * as vscode from "vscode";

interface SearchResult {
  memory: {
    id: string;
    type: string;
    title: string;
    content: string;
    source_type: string;
    source_url: string;
  };
  score: number;
  chunk_text: string;
}

async function apiCall(
  path: string,
  method: string,
  body?: unknown
): Promise<unknown> {
  const config = vscode.workspace.getConfiguration("omoikane");
  const baseUrl = config.get<string>("apiUrl", "http://localhost:8420");

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

function getProjectId(): string {
  const config = vscode.workspace.getConfiguration("omoikane");
  const projectId = config.get<string>("projectId", "");
  if (!projectId) {
    throw new Error(
      "Set omoikane.projectId in VS Code settings"
    );
  }
  return projectId;
}

export function activate(context: vscode.ExtensionContext) {
  const searchCmd = vscode.commands.registerCommand(
    "omoikane.search",
    async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search project memories",
        placeHolder: "e.g., how does authentication work",
      });

      if (!query) return;

      try {
        const projectId = getProjectId();
        const results = (await apiCall("/v1/search", "POST", {
          query,
          project_id: projectId,
          limit: 10,
        })) as SearchResult[];

        if (results.length === 0) {
          vscode.window.showInformationMessage("No results found");
          return;
        }

        const items = results.map((r) => ({
          label: `[${r.memory.type}] ${r.memory.title}`,
          description: `Score: ${r.score.toFixed(2)}`,
          detail: r.memory.content.substring(0, 200),
        }));

        const selected = await vscode.window.showQuickPick(items, {
          placeHolder: "Select a memory to view",
        });

        if (selected) {
          const result = results.find(
            (r) => r.memory.title === selected.label.replace(/^\[.*?\]\s/, "")
          );
          if (result) {
            const doc = await vscode.workspace.openTextDocument({
              content: result.memory.content,
              language: "markdown",
            });
            vscode.window.showTextDocument(doc);
          }
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`Search failed: ${msg}`);
      }
    }
  );

  const contextCmd = vscode.commands.registerCommand(
    "omoikane.context",
    async () => {
      const task = await vscode.window.showInputBox({
        prompt: "Describe your task",
        placeHolder: "e.g., implement rate limiting",
      });

      if (!task) return;

      try {
        const projectId = getProjectId();
        const result = (await apiCall("/v1/context", "POST", {
          task,
          project_id: projectId,
          limit: 5,
        })) as { context_block: string };

        const doc = await vscode.workspace.openTextDocument({
          content: result.context_block,
          language: "markdown",
        });
        vscode.window.showTextDocument(doc);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`Context assembly failed: ${msg}`);
      }
    }
  );

  const createMemoryCmd = vscode.commands.registerCommand(
    "omoikane.createMemory",
    async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Memory title",
      });
      if (!title) return;

      const type = await vscode.window.showQuickPick(
        ["decision", "pattern", "constraint", "context", "discussion"],
        { placeHolder: "Memory type" }
      );
      if (!type) return;

      const editor = vscode.window.activeTextEditor;
      const content = editor
        ? editor.document.getText(editor.selection)
        : await vscode.window.showInputBox({ prompt: "Memory content" });
      if (!content) return;

      try {
        const projectId = getProjectId();
        await apiCall("/v1/memories", "POST", {
          project_id: projectId,
          type,
          title,
          content,
        });
        vscode.window.showInformationMessage(`Memory created: ${title}`);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`Failed to create memory: ${msg}`);
      }
    }
  );

  const createADRCmd = vscode.commands.registerCommand(
    "omoikane.createADR",
    async () => {
      const title = await vscode.window.showInputBox({
        prompt: "ADR title",
        placeHolder: "e.g., Use PostgreSQL for primary database",
      });
      if (!title) return;

      const decision = await vscode.window.showInputBox({
        prompt: "What was decided?",
      });
      if (!decision) return;

      const context = await vscode.window.showInputBox({
        prompt: "Why was this decision needed?",
      });

      try {
        const projectId = getProjectId();
        await apiCall("/v1/decisions", "POST", {
          project_id: projectId,
          title,
          decision,
          context: context || "",
        });
        vscode.window.showInformationMessage(`ADR created: ${title}`);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        vscode.window.showErrorMessage(`Failed to create ADR: ${msg}`);
      }
    }
  );

  context.subscriptions.push(searchCmd, contextCmd, createMemoryCmd, createADRCmd);
}

export function deactivate() {}
