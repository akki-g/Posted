import { AppShell } from '@/components/AppShell';
import { AssistantChat } from '@/components/AssistantChat';

export default function AssistantScreen() {
  return (
    <AppShell
      title="Assistant"
      eyebrow="AI · BUDGETING & INVESTING"
      assistantContext="The user opened the full assistant workspace. Use their selected Money, Investing, or General section to decide which account and market tools are relevant.">
      <AssistantChat />
    </AppShell>
  );
}
