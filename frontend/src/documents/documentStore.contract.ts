import { useDocumentStore } from "../stores/documents";
import type {
  DocumentCategoryKey,
  DocumentFilters,
  DocumentItem,
  DocumentParseStatus,
  DocumentSummary
} from "../types/document";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const store = useDocumentStore();

type DocumentsAreDocumentItems = Assert<IsAssignable<typeof store.documents, DocumentItem[]>>;
type FilterShape = Assert<IsAssignable<typeof store.filters, DocumentFilters>>;
type SummaryShape = Assert<IsAssignable<typeof store.summary, DocumentSummary>>;
type CategoryShape = Assert<IsAssignable<(typeof store.categories)[number]["key"], DocumentCategoryKey>>;
type ParseStatusShape = Assert<IsAssignable<(typeof store.parseStatusOptions)[number]["value"], DocumentParseStatus | "all">>;

void store.categories;
void store.filteredDocuments;
void store.paginatedDocuments;
void store.totalPages;
void store.currentCategoryLabel;
void store.parseStatusOptions;
void store.enableStatusOptions;
void store.documentTypeOptions;
void store.setCategory("processing");
void store.setSearchKeyword("逆变器");
void store.setTypeFilter("PDF");
void store.setParseStatusFilter("failed");
void store.setEnableStatusFilter("enabled");
void store.setPage(2);
void store.resetFilters();
void store.loadDocuments();
void store.isLoading;
void store.isUploading;
void store.errorMessage;
void store.pendingDocumentIds;
void store.hasPendingDocumentActions;
void store.isDocumentPending("doc-inverter-manual");
void store.uploadDocumentFile(new File(["contract"], "contract.pdf", { type: "application/pdf" }));
void store.toggleDocumentEnabled("doc-inverter-manual");
void store.retryParse("doc-grid-failure");
void store.getFailureReason("doc-transformer-guide");
void (null as unknown as DocumentsAreDocumentItems);
void (null as unknown as FilterShape);
void (null as unknown as SummaryShape);
void (null as unknown as CategoryShape);
void (null as unknown as ParseStatusShape);
