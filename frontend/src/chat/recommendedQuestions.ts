import { Grid, TrendCharts } from "@element-plus/icons-vue";

export interface RecommendedQuestion {
  text: string;
  icon: typeof Grid;
  tone: "blue" | "cyan" | "orange";
}

export const recommendedQuestions: RecommendedQuestion[] = [
  { text: "逆变器效率如何提升？", icon: TrendCharts, tone: "blue" },
  { text: "光伏电站日常巡检有哪些内容？", icon: Grid, tone: "cyan" },
  { text: "并网电压异常如何处理？", icon: TrendCharts, tone: "orange" },
  { text: "组件热斑如何排查？", icon: Grid, tone: "blue" },
  { text: "低辐照下发电量下降原因？", icon: TrendCharts, tone: "orange" }
];
