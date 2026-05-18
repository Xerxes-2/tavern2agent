import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export function registerCommands(pi: ExtensionAPI) {
  pi.registerCommand("retry", {
    description: "撤销上一轮 agent 响应并重新发送最后一条用户消息",
    handler: async (_args, ctx) => {
      await ctx.waitForIdle();

      const entries = ctx.sessionManager.getEntries();
      let lastUserEntryId: string | null = null;
      let lastUserText: string | null = null;

      for (let i = entries.length - 1; i >= 0; i--) {
        const entry = entries[i];
        if (entry.type === "message" && (entry as any).message?.role === "user") {
          lastUserEntryId = entry.id;
          lastUserText = (entry as any).message.content?.[0]?.text;
          break;
        }
      }

      if (!lastUserEntryId || !lastUserText) {
        ctx.ui.notify("没有找到可重试的用户消息", "warning");
        return;
      }

      const result = await ctx.fork(lastUserEntryId, {
        withSession: async (ctx) => {
          ctx.ui.notify("🔄 重试中（已清除上一轮回复）...", "info");
          await ctx.sendUserMessage(lastUserText);
        },
      });

      if (result.cancelled) {
        ctx.ui.notify("重试被取消", "warning");
      }
    },
  });
}
