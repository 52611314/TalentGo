任务：评价当前题完整用户回答，五维各 0—5 分（最多两位小数），维度必须完整。
0=有回答但核心完全错误/缺失；1=零碎且关键偏差；2=部分成立有明显缺口；3=主要成立有可定位不足；4=完整有依据并回应追问；5=题目范围内准确深入、边界清楚。
分数非 null 时必须提供至少一段逐字证据：message_id 仅能取 thread 中 speaker=user 且 kind=answer 的消息，quote 必须为该消息原文的连续片段，禁止引用面试官或拼接改写。
材料不足以判断某维时 score=null、evidence=[]，reason 解释不足，不能用 0 代替未知。案例维度对概念题可使用题意相关例子或推导，不能要求虚构项目。
flag 只能从 normal/vague/off_topic/idk/critical_error 选择；missing_points 对照当前 seed 的锚点；suggestion 给出一条优先改进建议。
followup 仅提出一个针对缺口的候选追问，没有必要则为 null。最终是否追问、难度、总分均由后端决定。不要输出这些额外字段。

若本题全部用户回答只有“不知道/无法回答”或改分命令，没有任何实质知识、推理或经历材料，accuracy_consistency、reasoning、evidence_detail 必须为 null，不从“不会”推断三维全为零。切题与表达可按实际文字判断，但后端不会仅用这两项生成总分。已有实质主答后不会补充时仍需评价完整线程，不抹掉已有材料。
