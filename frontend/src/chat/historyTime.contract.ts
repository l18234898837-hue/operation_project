import { formatConversationHistoryTime, getConversationHistoryGroup, useChatStore } from "../stores/chat";
import type { ConversationHistoryItem } from "../stores/chat";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const timestamp = new Date("2026-06-28T14:30:00+08:00").getTime();
const formattedTime: string = formatConversationHistoryTime(timestamp);
const groupLabel: string = getConversationHistoryGroup(timestamp);
const store = useChatStore();

type HistoryGroupItemsAreDerived = Assert<
  IsAssignable<(typeof store.historyGroups)[number]["items"][number], ConversationHistoryItem>
>;

void formattedTime;
void groupLabel;
void (null as unknown as HistoryGroupItemsAreDerived);
