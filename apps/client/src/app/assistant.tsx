import { useLocalSearchParams } from 'expo-router';

import { AppShell } from '@/components/AppShell';
import { AssistantChat } from '@/components/AssistantChat';
import type { AssistantSection } from '@/lib/assistantSection';

const VALID_SECTIONS: AssistantSection[] = ['general', 'money', 'investing'];

export default function AssistantScreen() {
  const { section } = useLocalSearchParams<{ section?: string }>();
  const initialSection = VALID_SECTIONS.includes(section as AssistantSection)
    ? (section as AssistantSection)
    : undefined;

  return (
    <AppShell
      title="Assistant"
      eyebrow="AI · BUDGETING & INVESTING"
      assistantContext="The user opened the full assistant workspace. Use their selected Money, Investing, or General section to decide which account and market tools are relevant.">
      <AssistantChat initialSection={initialSection} />
    </AppShell>
  );
}
