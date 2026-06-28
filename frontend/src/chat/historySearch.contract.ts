import { useChatStore, type ConversationHistoryItem } from "../stores/chat";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const store = useChatStore();

type HistoryItemsCarrySearchContext = Assert<
  IsAssignable<
    (typeof store.historyGroups)[number]["items"][number],
    ConversationHistoryItem & {
      matchedMessageSnippet: string | null;
      matchType: "title" | "message" | "title_message" | null;
    }
  >
>;
type SearchResultCountIsNumber = Assert<IsAssignable<typeof store.historySearchResultCount, number>>;
type IsHistorySearchingIsBoolean = Assert<IsAssignable<typeof store.isHistorySearching, boolean>>;

store.historyQuery = "热斑";
store.clearHistorySearch();

void (null as unknown as HistoryItemsCarrySearchContext);
void (null as unknown as SearchResultCountIsNumber);
void (null as unknown as IsHistorySearchingIsBoolean);
