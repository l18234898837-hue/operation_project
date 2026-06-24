import type { QaAskRequest, QaAskResponse, QaReference, QaStreamEvent } from "./qa";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;
type BackendSessionId = `${string}-${string}-${string}-${string}-${string}`;

type RequestSessionIdIsBackendUuid = Assert<IsAssignable<NonNullable<QaAskRequest["session_id"]>, BackendSessionId>>;
type ResponseIncludesBackendSessionId = Assert<IsAssignable<QaAskResponse, { session_id: BackendSessionId }>>;
type ReferenceIncludesDocumentFileName = Assert<IsAssignable<QaReference, { document_file_name: string | null }>>;
type ReferenceIncludesVisibility = Assert<IsAssignable<QaReference, { visible: boolean }>>;
type StreamEventIncludesAnswerDelta = Assert<IsAssignable<{ event: "answer_delta"; data: { text: string } }, QaStreamEvent>>;

void (null as unknown as RequestSessionIdIsBackendUuid);
void (null as unknown as ResponseIncludesBackendSessionId);
void (null as unknown as ReferenceIncludesDocumentFileName);
void (null as unknown as ReferenceIncludesVisibility);
void (null as unknown as StreamEventIncludesAnswerDelta);
