import { useSyncExternalStore } from 'react';

export type AssistantSection = 'money' | 'investing' | 'general';

let current: AssistantSection = 'general';
const listeners = new Set<() => void>();

export function setAssistantSection(section: AssistantSection): void {
  if (current === section) return;
  current = section;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): AssistantSection {
  return current;
}

export function useAssistantSection(): AssistantSection {
  return useSyncExternalStore(subscribe, getSnapshot);
}
