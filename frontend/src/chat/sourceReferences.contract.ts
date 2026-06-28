import type { Component } from "vue";

import SourceReferences from "../components/chat/SourceReferences.vue";
import type { AnswerTypeDescription } from "./qaPresentation";

type Assert<T extends true> = T;
type HasSourceAnswerMetaProps<TComponent> = TComponent extends new () => {
  $props: {
    answerDescription: AnswerTypeDescription;
    confidence: number | null;
  };
}
  ? true
  : false;

type SourceReferencesCarriesAnswerMeta = Assert<HasSourceAnswerMetaProps<typeof SourceReferences>>;
type SourceReferencesIsComponent = Assert<typeof SourceReferences extends Component ? true : false>;

void (null as unknown as SourceReferencesCarriesAnswerMeta);
void (null as unknown as SourceReferencesIsComponent);
