import type { Conversation } from "./conversationModel";

export const initialConversations: Conversation[] = [
  {
    id: "inverter-efficiency",
    title: "逆变器效率如何提升？",
    time: "14:32",
    group: "今天",
    status: "answered",
    messages: [
      {
        id: "inverter-efficiency-user",
        role: "user",
        content: "逆变器效率如何提升？",
        createdAt: "14:32"
      },
      {
        id: "inverter-efficiency-assistant",
        role: "assistant",
        content:
          "提升逆变器效率通常需要从设备选型、运行区间、散热条件、组串匹配和定期维护几方面综合优化。当前知识库接口未完成模型配置时，本条作为历史会话示例展示。",
        createdAt: "14:33"
      }
    ]
  },
  {
    id: "daily-inspection",
    title: "光伏电站日常巡检有哪些内容？",
    time: "11:20",
    group: "今天",
    status: "answered",
    messages: [
      {
        id: "daily-inspection-user",
        role: "user",
        content: "光伏电站日常巡检有哪些内容？",
        createdAt: "11:20"
      },
      {
        id: "daily-inspection-assistant",
        role: "assistant",
        content:
          "日常巡检应覆盖组件外观、支架与紧固件、汇流箱、逆变器运行状态、线缆接头、接地、防雷、环境遮挡和告警记录。发现异常后应记录位置、时间和现象，便于后续追踪。",
        createdAt: "11:21"
      }
    ]
  },
  {
    id: "grid-voltage",
    title: "并网电压异常如何处理？",
    time: "10:05",
    group: "今天",
    status: "answered",
    messages: []
  },
  {
    id: "hot-spot",
    title: "组件热斑如何排查？",
    time: "09:15",
    group: "今天",
    status: "answered",
    messages: []
  },
  {
    id: "low-irradiance",
    title: "低辐照条件下发电量下降原因？",
    time: "16:42",
    group: "昨天",
    status: "answered",
    messages: []
  },
  {
    id: "combiner-temperature",
    title: "汇流箱温度过高如何处理？",
    time: "15:33",
    group: "昨天",
    status: "answered",
    messages: []
  },
  {
    id: "harmonic",
    title: "光伏系统谐波影响及治理措施",
    time: "06/01",
    group: "更早",
    status: "answered",
    messages: []
  },
  {
    id: "alarm-codes",
    title: "逆变器告警代码大全",
    time: "05/30",
    group: "更早",
    status: "answered",
    messages: []
  },
  {
    id: "cleaning-cycle",
    title: "光伏组件清洗周期建议",
    time: "05/28",
    group: "更早",
    status: "answered",
    messages: []
  }
];
