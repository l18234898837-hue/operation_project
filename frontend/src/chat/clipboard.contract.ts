import { copyTextToClipboard, type CopyResult } from "./clipboard";

type Assert<T extends true> = T;
type IsAssignable<TValue, TExpected> = TValue extends TExpected ? true : false;

const result = copyTextToClipboard("需要复制的回答");

type CopyReturnsResult = Assert<IsAssignable<Awaited<typeof result>, CopyResult>>;

void result;
void (null as unknown as CopyReturnsResult);
