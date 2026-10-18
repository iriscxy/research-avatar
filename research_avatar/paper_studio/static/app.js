const $ = (id) => document.getElementById(id);
const requestedUiLanguage = new URLSearchParams(window.location.search).get("lang");
const embeddedInResearchStudio = new URLSearchParams(window.location.search).get("embedded") === "research-studio";
const studioUiLanguage = requestedUiLanguage === "en"
  ? "en"
  : (requestedUiLanguage === "zh" ? "zh" : (localStorage.getItem("research-avatar-language") === "en" ? "en" : "zh"));
const studioT = (zh, en) => studioUiLanguage === "en" ? en : zh;
if (embeddedInResearchStudio) document.documentElement.classList.add("research-studio-embedded");
const studioTranslations = new Map(Object.entries({
  "界面语言":"Interface language", "写作模型":"Writing model", "应用":"Apply", "安全更换 API Key":"Update API key securely",
  "请为当前选择的正文写作 API 在启动 Paper Studio 的本机终端配置；不要把真实 key 输入聊天、提交到仓库或保存在浏览器中。GPT Image 仍单独使用 OpenAI。":"Configure the selected prose-writing API in the local terminal that starts Paper Studio. Never paste a real key into chat, commit it, or store it in the browser. GPT Image still uses OpenAI separately.",
  "网页未提供的功能或其他需求，请在本地终端运行 Code Agent。":"For features not available in the web interface, run Code Agent in your local terminal.",
  "正文":"Prose", "图":"Figures", "表":"Tables", "编译 PDF":"Compile PDF", "清空生成内容":"Clear generated content", "下载项目 ZIP":"Download project ZIP",
  "写论文需要 LLM API":"Paper writing requires an LLM API", "然后停止当前服务并重新运行":"Then stop the current service and run it again",
  "Paper Studio 已启动，尚未载入论文":"Paper Studio is running with no paper loaded", "Paper Studio 状态加载失败":"Failed to load Paper Studio state",
  "将项目配置、段落计划、LaTeX 与图表数据写入 paper/ 后，固定网页会自动读取这些内容。":"Once project configuration, paragraph plans, LaTeX, and artifact data are written to paper/, this interface loads them automatically.",
  "直接生成全文初稿":"Generate full first draft", "复用已批准的段落结构、结果与逐段校验，只补齐尚未写入的段落。":"Use the approved paragraph structure, results, and paragraph checks to fill only unwritten paragraphs.",
  "⏸ 停止":"⏸ Stop", "论文标题":"Paper title", "当前标题 / 可编辑候选标题":"Current title / editable candidate", "输入论文标题":"Enter a paper title",
  "GPT 生成候选标题":"Generate title candidates", "确认写入 LaTeX":"Write to LaTeX", "选择当前编辑的自然段":"Select the paragraph to edit",
  "例如：更突出 representation contraction，保持审慎，不增加未验证 claim。":"For example: emphasize representation contraction, remain cautious, and add no unverified claims.",
  "一键生成当前 Section":"Generate current section", "参考论文中对应的写法":"Corresponding writing move in the reference paper",
  "目标段落规划（写作约束）":"Target paragraph plan (writing constraints)", "查看参考原文":"View reference text", "当前候选段落":"Current candidate paragraph",
  "给 GPT 的修改意见":"Revision instructions for GPT", "根据 comment 修改":"Revise from comment", "Accept → LaTeX":"Accept → LaTeX",
  "系统正在结合已批准的段落结构、working abstract 和实验结果生成当前段落…":"The system is generating this paragraph from the approved structure, working abstract, and experiment results…",
  "例如：motivation 太泛；把三个 confound 说清楚，缩短最后一句。":"For example: the motivation is too broad; clarify the three confounds and shorten the last sentence.",
  "第 — / — 页":"Page — / —", "下载 PDF":"Download PDF", "显示导航栏":"Show navigation", "隐藏导航栏":"Hide navigation",
  "还没有可预览的 PDF":"No PDF is available yet", "outline 确认并生成 LaTeX scaffold 后，这里会随每次 Accept 自动刷新。":"After the outline is approved and the LaTeX scaffold is generated, this preview refreshes after every Accept.",
  "按论证依赖推进图表":"Build artifacts in argument order", "机制图单独设计；数据图和表格都从 results/ 生成，确认后插入对应自然段。":"Design mechanism figures separately; generate data figures and tables from results/, then insert them into the linked paragraph after approval.",
  "选择一张图":"Select a figure", "修改命令":"Revision request", "调用本地 Agent":"Call local Agent", "⏸ 停止调用":"⏸ Stop request",
  "绘图前置步骤":"Figure prerequisite", "画图 Prompt":"Figure prompt", "GPT Image 将按这里的完整描述绘制":"GPT Image renders the complete description entered here.",
  "GPT 生成的画图 Prompt":"GPT-generated figure prompt", "修改 Prompt":"Revise prompt", "描述希望 GPT 怎样调整左侧 Prompt":"Describe how GPT should revise the prompt on the left.",
  "给 GPT 的 Prompt 修改指令":"Prompt revision instructions", "GPT 生成画图 Prompt":"Generate figure prompt", "确认 Prompt 后绘图":"Approve prompt and draw",
  "确认后依次完成 GPT Image 绘制和可编辑 PowerPoint 重建":"After approval, generate the GPT Image and rebuild it as an editable PowerPoint.",
  "待生成":"Pending", "等待 Prompt":"Waiting for prompt", "可编辑 PPT/PDF":"Editable PPT/PDF", "随后自动重建":"Rebuilt automatically next",
  "确认 Prompt → GPT Image":"Approve prompt → GPT Image", "重试可编辑 PPT/PDF 重建":"Retry editable PPT/PDF rebuild",
  "这张图的修改 Prompt":"Revision prompt for this figure", "本地 Agent 生成这张图":"Generate this figure with local Agent", "合成设置":"Composition settings",
  "论文组合 Prompt":"Paper composition prompt", "合成图":"Compose figure", "Agent 解析的布局计划":"Agent-parsed layout plan", "显示 GPT 原图":"Show original GPT image",
  "图片 Caption":"Figure caption", "给 GPT 的 Caption 修改 Prompt":"Caption revision prompt", "GPT 生成 Caption candidate":"Generate caption candidate",
  "描述这张图所展示的内容和必要的实验条件。":"Describe what the figure shows and any necessary experimental conditions.",
  "当前正文将使用此 Caption":"The paper will use this caption", "保存 Caption":"Save caption", "插入正文位置":"Insertion point", "排版方式":"Layout", "单栏":"Single column", "双栏":"Two columns",
  "确认并插入正文":"Approve and insert into paper", "高级：生成新的表格初稿":"Advanced: generate a new table draft",
  "初始表格规格":"Initial table specification", "本地 Agent 生成初稿":"Generate draft with local Agent", "可编辑 Table LaTeX":"Editable table LaTeX",
  "保存修改":"Save changes", "取消":"Cancel", "确认清空":"Confirm clearing", "复制 ID":"Copy ID", "当前项目 ID（可选择复制）":"Current project ID (copy if needed)",
  "粘贴或输入项目 ID 以确认":"Paste or enter the project ID to confirm", "服务商":"Provider", "安全更新":"Update securely",
  "这会删除当前项目的生成正文、候选、对话和图表产物，但保留配置、输入与实验结果。":"This deletes generated prose, candidates, conversations, and artifacts for the current project while preserving configuration, inputs, and experiment results.",
  "密钥只写入当前 Paper Studio 进程内存，不进入聊天记录、浏览器存储或项目文件。":"The key is stored only in the current Paper Studio process memory, never in chat, browser storage, or project files."
  ,"参考论文：":"Reference paper: ", "正文已全部写入 LaTeX；请在图表工作台完成并确认：":"All prose has been written to LaTeX; complete and approve these artifacts in the figure and table workspace: ",
  "全文初稿已生成":"Full first draft generated", "已写入 PDF":"Written to PDF", "修改后需确认，才会写入 LaTeX。":"Approve revisions before writing them to LaTeX.",
  "当前 Section 已完成":"Current section is complete", "参考摘要先提出假设，解释现象，再给出验证。":"The reference abstract introduces the hypothesis, explains the phenomenon, and then presents validation.",
  "参考摘要先说明问题，再提出假设，最后总结验证。":"The reference abstract states the problem, introduces the hypothesis, and closes with the validation.",
  "仅向当前目标段落提供 EXP PLAN 中已批准并嵌入的参考原文，用于模仿论证动作，不复制研究结论或措辞。":"Only the approved reference excerpt embedded in the experiment plan is provided for the current target paragraph. It guides the argumentative move, not the research claims or wording.",
  "参考论文先说明问题重要性，再收窄到尚未解决的矛盾。":"The reference paper establishes the importance of the problem, then narrows to the unresolved tension.",
  "参考论文先综述方法，再综述理论，最后定位自身。":"The reference paper reviews methods, then theory, and finally positions its own contribution.",
  "参考论文先概述方法，再定义过程，最后说明细节。":"The reference paper gives an overview, defines the procedure, and then specifies implementation details.",
  "参考论文先描述设置，再给出结果，最后分析。":"The reference paper describes the setup, presents results, and then analyzes them.",
  "参考论文讨论可预测性，并指出不可预测的部分。":"The reference paper discusses predictability and identifies what remains unpredictable.",
  "参考论文总结贡献，指出意义，并列出未来方向。":"The reference paper summarizes its contributions, implications, and future directions.",
  "已接受版本（可继续修改）":"Accepted version (editable)", "已写入 LaTeX":"Written to LaTeX",
  "机制图 · 先完成":"Mechanism figure · complete first", "画图 Prompt 任务已开始…":"Figure-prompt task started…", "生成中":"Generating",
  "Caption 已在接受 I-P1 时自动生成":"The caption was generated automatically when I-P1 was accepted", "Wrapfigure（AAAI 禁用）":"Wrapfigure (disabled for AAAI)",
  "结果表 · 可编辑 LaTeX":"Results table · editable LaTeX", "正在启动本地 Codex agent 生成表格初稿…":"Starting the local Agent to draft the table…",
  "上方图片由当前 LaTeX 真实编译。初稿与实验结果相关修改均由本地 Agent 完成。":"The preview above is compiled from the current LaTeX. The local Agent creates the draft and applies result-grounded revisions.",
  "本地 Agent 已启动，正在从可追溯结果生成 LaTeX 表格。":"The local Agent is generating a LaTeX table from traceable results.",
  "正在自动生成 T1 表格初稿…":"Automatically generating the initial T1 table…"
  ,"请先确认 outline；批量模式不会绕过论文结构确认。":"Confirm the outline first; batch drafting does not bypass structure approval."
  ,"请先按页面顶部说明配置 LLM API Key。":"Configure the LLM API key using the instructions at the top of the page."
  ,"继续补齐未完成正文":"Continue unfinished prose"
  ,"尚未载入论文":"No paper loaded"
  ,"完成":"Complete"
  ,"未找到标题":"No title found"
  ,"查看参考原文":"View reference text"
  ,"显示导航栏":"Show navigation"
  ,"隐藏导航栏":"Hide navigation"
  ,"加载失败":"Loading failed"
  ,"已写入 PDF":"Written to PDF"
  ,"线上仅保留正文、可编辑表格与 Python 数据图；其他图以带 Caption 和 label 的 placeholder 写入论文。":"The online version supports prose, editable tables, and Python data plots. Other figures are inserted as placeholders with captions and labels."
  ,"这是只读 Demo，无法生成或修改内容。":"This is a read-only demo; content cannot be generated or modified."
  ,"等待 candidate":"Waiting for candidate"
  ,"当前版本已写入 LaTeX；可直接修改正文，或填写 comment 让写作模型生成新 candidate。":"The current version is in LaTeX. Edit it directly or add a comment for GPT to generate a new candidate."
  ,"正在结合已批准的段落结构、working abstract 和实验结果生成当前段落…":"Generating the current paragraph from the approved structure, working abstract, and experiment results…"
  ,"确认后更新 LaTeX 并重新编译 PDF。":"Update LaTeX and recompile the PDF after confirmation."
  ,"当前标题已经写入 PDF。":"The current title is already in the PDF."
  ,"模型 candidate 尚未保存；可编辑后确认。":"The GPT candidate is unsaved; edit it and confirm when ready."
  ,"提炼后的参考结构":"Distilled reference structure"
  ,"双击正文、图片或表格，返回对应编辑位置":"Double-click prose, a figure, or a table to return to its editor"
  ,"正在定位 PDF 中的源内容…":"Locating the source content in the PDF…"
  ,"已就绪":"Ready"
  ,"绘制中":"Drawing"
  ,"已归档":"Archived"
  ,"自动重建中":"Rebuilding automatically"
  ,"已完成":"Completed"
  ,"Prompt 未变 → 显示原图":"Prompt unchanged → Show original"
  ,"确认新 Prompt → 重新调用 GPT Image":"Approve new prompt → Call GPT Image again"
  ,"重新解析 Prompt 并生成合成图":"Reparse prompt and regenerate composition"
  ,"更新 Caption → PDF":"Update caption → PDF"
  ,"补生成 Caption → PDF":"Generate missing caption → PDF"
  ,"已插入正文":"Inserted into paper"
  ,"重新插入":"Insert again"
  ,"保存修改（需重新确认）":"Save changes (confirmation required)"
  ,"更新表格 → PDF":"Update table → PDF"
  ,"保存 Caption 并更新 PDF":"Save caption and update PDF"
  ,"例如：缩短标题，把图例移到右上角；只调整这一张图，不改变数据。":"For example: shorten the title and move the legend to the upper right; adjust only this panel without changing the data."
  ,"这张图的修改 Prompt":"Revision prompt for this figure"
  ,"这张子图的修改 Prompt":"Revision prompt for this panel"
  ,"尚未生成这张图":"This figure has not been generated"
  ,"尚未生成这张独立子图":"This panel has not been generated"
  ,"本地 Agent 正在处理这张图…":"The local Agent is processing this figure…"
  ,"本地 Agent 正在处理这张子图…":"The local Agent is processing this panel…"
  ,"本地 Agent 重新生成这张":"Regenerate with local Agent"
  ,"这是一张独立单图：点击下方按钮后直接生成最终 PDF candidate，不添加子图角标。":"This is a standalone figure. The button below generates the final PDF candidate directly, without panel labels."
  ,"请分别生成并检查每张 PDF candidate。全部满意后，再手动点击“合成图”生成 PPTX 与矢量 PDF candidate。":"Generate and review each PDF candidate separately. When all are satisfactory, click Compose figure to create the PPTX and vector PDF candidate."
  ,"线上不提供画图表功能":"Figure and table drawing is unavailable online"
  ,"来源图 · 参考论文证据":"Source figure · reference-paper evidence"
  ,"数据图 · results/ 驱动":"Data figure · driven by results/"
  ,"生成表格初稿":"Generate table draft"
  ,"当前候选段落":"Current candidate paragraph"
  ,"已接受并写入 LaTeX 的 section 内容":"Accepted section content written to LaTeX"
  ,"未上传实验结果：本 section 只保留段落主旨和待执行实验，不生成正文。":"No experimental results were uploaded. This section keeps only paragraph purposes and planned experiments, without drafting prose."
  ,"这是当前写入 LaTeX 的版本；填写 comment 后可继续修改。":"This is the version currently written to LaTeX; add a comment to revise it."
  ,"等待生成当前段落…":"Waiting to generate the current paragraph…"
  ,"这个 section 已完成。":"This section is complete."
  ,"未上传实验结果：从 Experiments 开始仅展示每段主旨、写作任务和待执行实验，不调用 LLM 生成正文。":"No experimental results were uploaded. From Experiments onward, only paragraph purposes, writing tasks, and planned experiments are shown; the LLM does not draft prose."
  ,"Outline 尚未确认。可以浏览界面，但在确认并建立 LaTeX scaffold 前不能 Accept → LaTeX。":"The outline is not confirmed. You may browse, but cannot accept content into LaTeX until the scaffold is created."
  ,"当前段落完成后自动生成本 Section…":"Generate this section automatically after the current paragraph…"
  ,"正在根据 comment 修改当前段落…":"Revising the current paragraph from the comment…"
  ,"后台 candidate 已生成；已保留你正在编辑的正文，Accept 时将以编辑框内容为准。":"A background candidate is ready. Your current edits were preserved and will be used on Accept."
  ,"当前段落已生成。你只需要写 comment 修改，或 Accept → LaTeX。":"The current paragraph is ready. Add a comment to revise it or accept it into LaTeX."
  ,"已接受版本的手动修改（尚未写入）":"Manual edits to the accepted version (not yet written)"
  ,"请先输入写作模型名称。":"Enter a writing model first."
  ,"标题有未保存修改。":"The title has unsaved changes."
  ,"请先填写 Title GPT Prompt。":"Enter the Title GPT Prompt first."
  ,"正在生成标题候选；不会自动保存…":"Generating title candidates; they will not be saved automatically…"
  ,"正在写入 LaTeX 并编译 PDF…":"Writing to LaTeX and compiling the PDF…"
  ,"正在核对最新段落状态…":"Checking the latest paragraph state…"
  ,"候选已在另一轮生成中更新；已自动载入最新版，请确认内容后再次 Accept。":"The candidate changed in another generation run. The latest version is loaded; review it before accepting again."
  ,"当前段落没有可接受的正文。":"The current paragraph has no prose to accept."
  ,"正在校验引用；缺失时会联网检索、更新 BibTeX，再写入 LaTeX 并编译…":"Validating citations; missing references will be retrieved, added to BibTeX, written to LaTeX, and compiled…"
  ,"正在编译 LaTeX…":"Compiling LaTeX…"
  ,"PDF 编译成功。":"PDF compiled successfully."
  ,"项目 ID 不匹配；未删除任何生成内容。":"Project ID does not match; nothing was deleted."
  ,"当前没有可清空的论文项目。":"There is no paper project to clear."
  ,"项目 ID 已复制。":"Project ID copied."
  ,"自动复制失败；ID 已选中，请按 Ctrl/Cmd+C。":"Automatic copy failed. The ID is selected; press Ctrl/Cmd+C."
  ,"全文初稿任务已启动；可以切换页面查看进度，完成后仍可逐段修改。":"Full-draft generation has started. You may navigate elsewhere and edit paragraphs after it completes."
  ,"全文初稿与全部图表已写入 LaTeX，并完成 PDF 编译。":"The full draft and all artifacts were written to LaTeX, and the PDF was compiled."
  ,"全文初稿已写入 LaTeX 并完成 PDF 编译，计划图表已以 placeholder 保留。":"The full draft was written to LaTeX and compiled to PDF; planned figures and tables remain as placeholders."
  ,"已请求停止；已完成段落保留，之后可继续补齐未完成正文。":"Stop requested. Completed paragraphs are preserved and unfinished prose can be resumed later."
  ,"完成。":"Done."
  ,"正在停止本次 Codex 绘图任务…":"Stopping this GPT Image request…"
  ,"正在生成 Caption…":"GPT is generating a caption…"
  ,"正在生成 Caption candidate…":"Generating a caption candidate…"
  ,"Caption 已保存。":"Caption saved."
  ,"正在安全更新…":"Updating securely…"
  ,"GPT candidate 尚未保存；可继续编辑，确认后再写入 LaTeX。":"The GPT candidate is unsaved; edit it and confirm before writing it to LaTeX."
  ,"标题已确认写入 LaTeX，并完成 PDF 编译。":"The title was written to LaTeX and the PDF was compiled."
  ,"网页版保留图位、图题和正文引用，但不直接绘制机制图；请下载项目 ZIP，并在本地终端运行 Code Agent 完成绘图。":"The web version preserves the figure location, caption, and prose reference but does not draw mechanism figures. Download the project ZIP and use Code Agent locally to complete the figure."
  ,"线上版以带 Caption 和 label 的 placeholder 保留该图位，不提供正式绘图。完整功能请下载项目 ZIP 后在本地版使用。":"The online version preserves this figure as a placeholder with its caption and label; formal drawing is unavailable. Download the project ZIP and use the local version for the complete workflow."
  ,"线上版以带 Caption 和 label 的 placeholder 保留该表位，不提供表格生成。完整功能请下载项目 ZIP 后在本地版使用。":"The online version preserves this table as a placeholder with its caption and label; table generation is unavailable. Download the project ZIP and use the local version for the complete workflow."
  // English text taken from the interface as shipped before the Chinese restore; later keys override earlier ones.
  ,"写作模型":"Writing model"
  ,"应用":"Apply"
  ,"安全更换 API Key":"Update API key"
  ,"网页未提供的功能或其他需求，请在本地终端运行 Code Agent。":"Features not provided by the webpage or other requests should be run with Code Agent in the local terminal."
  ,"正文":"Prose"
  ,"图":"Figures"
  ,"表":"Tables"
  ,"编译 PDF":"Compile PDF."
  ,"清空生成内容":"Clear generated content"
  ,"下载项目 ZIP":"Download project ZIP"
  ,"写论文需要 LLM API":"Writing a paper requires an LLM API."
  ,"请为当前选择的正文写作 API 在启动 Paper Studio 的本机终端配置；不要把真实 key 输入聊天、提交到仓库或保存在浏览器中。":"Configure the writing API for the current selected text in the local terminal to start Paper Studio; do not input real keys into chat, submit to repositories, or store in the browser."
  ,"export OPENAI_API_KEY=\"粘贴你的 API key\"":"export OPENAI_API_KEY=\"Paste your API key.\""
  ,"然后停止当前服务并重新运行":"Then stop the current service and restart."
  ,"Paper Studio 已启动，尚未载入论文":"Paper Studio Started, the paper has not yet loaded."
  ,"将项目配置、段落计划、LaTeX 与图表数据写入":"Write project configuration, paragraph plan, LaTeX and chart data."
  ,"后，固定网页会自动读取这些内容。":"Thereafter, the static webpage will automatically read these contents."
  ,"空壳启动命令：":"Bare-bones startup command:"
  ,"Paper Studio 状态加载失败":"Paper Studio Status load failed"
  ,"直接生成全文初稿":"Directly generate the full draft."
  ,"复用已批准的段落结构、结果与逐段校验，只补齐尚未写入的段落。":"Reuse approved paragraph structure, results, and per paragraph validation, filling only the sections not yet written."
  ,"⏸ 停止":"⏸ stop"
  ,"论文标题":"Paper title"
  ,"当前标题 / 可编辑候选标题":"Current title / editable candidate titles."
  ,"输入论文标题":"Enter paper title"
  ,"标题生成指令":"Title-generation instructions"
  ,"例如：更突出 representation contraction，保持审慎，不增加未验证 claim。":"For example, emphasize representation contraction, remain cautious, do not add unverified claims."
  ,"生成候选标题":"Generate candidate titles"
  ,"确认写入 LaTeX":"Confirm writing to LaTeX"
  ,"选择当前编辑的自然段":"Select the currently edited paragraph."
  ,"一键生成当前 Section":"One-click generation of the current section."
  ,"参考论文中对应的写法":"The corresponding formulation in the reference papers."
  ,"目标段落规划（写作约束）":"Target paragraph planning (writing constraints)."
  ,"查看参考原文":"View referenced original text."
  ,"当前候选段落":"Current candidate paragraph."
  ,"系统正在结合已批准的段落结构、working abstract 和实验结果生成当前段落…":"The system is combining approved paragraph structure working abstract and experimental results to generate the current paragraph."
  ,"给写作模型的修改意见":"Feedback to the writing model"
  ,"例如：motivation 太泛；把三个 confound 说清楚，缩短最后一句。":"For example, motivation is too generic; clarify three confounds and shorten the last sentence."
  ,"根据 comment 修改":"Modify according to comment."
  ,"第 — / — 页":"Page — / —"
  ,"下载 PDF":"Download PDF"
  ,"显示导航栏":"Show navigation bar."
  ,"还没有可预览的 PDF":"No PDF available for preview yet."
  ,"outline 确认并生成 LaTeX scaffold 后，这里会随每次 Accept 自动刷新。":"outline After confirming and generating the LaTeX scaffold, this will automatically refresh with every Accept."
  ,"PDF 页面导航":"PDF Page navigation"
  ,"双击正文或图表可返回编辑":"Double click the main text or charts to return to editing."
  ,"按论证依赖推进图表":"Advance charts according to argument dependencies"
  ,"机制图单独设计；数据图和表格都从 results/ 生成，确认后插入对应自然段。":"Mechanism diagrams designed separately; data plots and tables are generated from results/ and inserted into the corresponding paragraph after confirmation."
  ,"选择一张图":"Select a figure."
  ,"修改命令":"Modify command"
  ,"例如：把两个 benchmark 做成分组表头；我们的方法放最后并加粗；在 caption 中说明 ASR 和 StrongREJECT 都是跨模型平均值。不要改变任何数值。":"Example: arrange the two benchmarks as grouped headers; place our method last and bold it; in the caption note that ASR and StrongREJECT are cross model averages. Do not modify any values."
  ,"调用本地 Agent":"Invoke local Agent"
  ,"⏸ 停止调用":"⏸ Stop calling"
  ,"绘图前置步骤":"Drawing prerequisites"
  ,"画图 Prompt":"Plotting prompt"
  ,"Codex 将按这里的完整描述绘制原生可编辑图形":"The local Agent will render native editable graphics according to this complete description."
  ,"模型生成的画图 Prompt":"Model-generated drawing prompt"
  ,"先生成画图 Prompt；可以直接修改左侧完整 Prompt，也可以在右侧输入修改指令。":"First generate the drawing prompt; you can directly modify the complete prompt on the left or enter modification commands on the right."
  ,"修改 Prompt":"Modify prompt"
  ,"描述希望模型怎样调整左侧 Prompt":"Describe how you want the model to adjust the prompt on the left."
  ,"画图 Prompt 修改指令":"Drawing-prompt revision instructions"
  ,"例如：当前内容太多；改成适合单栏的简单图，只保留两个核心模块，减少文字。":"For example the current content is too long; replace with a simple single column graphic, keep only two core modules, reduce text."
  ,"生成画图 Prompt":"Generate drawing prompt"
  ,"确认 Prompt 后绘图":"Plot after confirming the Prompt."
  ,"确认后由 Codex 直接生成可编辑 PowerPoint 和论文 PDF":"Upon confirmation, the local Agent directly generates editable PowerPoint and the paper PDF."
  ,"机制图生成流程":"Mechanism diagram generation process"
  ,"待生成":"To be generated"
  ,"Codex 原生图形":"Native graphics"
  ,"等待 Prompt":"Waiting for Prompt"
  ,"可编辑 PPT/PDF":"Editable PPT/PDF."
  ,"随后自动重建":"Then automatically rebuild."
  ,"确认 Prompt → Codex 绘图":"Confirm prompt → draw"
  ,"重试可编辑 PPT/PDF 重建":"Retry editable PPT/PDF reconstruction."
  ,"请分别生成并检查每张 PDF candidate。全部满意后，再手动点击“合成图”生成 PPTX 与矢量 PDF candidate。":"Please generate and review each PDF candidate separately. When all are satisfactory, manually click Synthesize Figure to generate PPTX and vector PDF candidates."
  ,"这张图的修改 Prompt":"Modification prompt for this figure."
  ,"例如：缩短标题，把图例移到右上角；只调整这张图，不改变数据。":"For example shorten the title and move the legend to the upper right corner; only adjust this figure and do not change the data."
  ,"本地 Agent 生成这张图":"Local agent generated this figure."
  ,"合成设置":"Synthesis settings"
  ,"论文组合 Prompt":"Paper composition prompt."
  ,"合成图":"Composite figure"
  ,"Agent 解析的布局计划":"Agent Parsed layout plan"
  ,"显示构图草稿":"Show composition draft"
  ,"图片 Caption":"Image caption"
  ,"描述这张图所展示的内容和必要的实验条件。":"Describe what this figure shows and the required experimental conditions."
  ,"Caption 修改指令":"Caption-revision instructions"
  ,"例如：解释三条曲线分别对应什么；压缩为一句短句；保留 synthetic 声明。":"For example, explain what each of three curves represents; compress to one sentence; retain the synthetic declaration."
  ,"生成 Caption candidate":"Generate caption candidate"
  ,"当前正文将使用此 Caption":"The current main text will use this caption."
  ,"保存 Caption":"Save caption"
  ,"插入正文位置":"Body text insertion point"
  ,"排版方式":"Typesetting method"
  ,"单栏":"single-column"
  ,"双栏":"two-column"
  ,"Wrapfigure（AAAI 禁用）":"Wrapfigure(AAAI Disable)"
  ,"确认并插入正文":"Confirm and insert the body text"
  ,"上方图片由当前 LaTeX 真实编译。初稿与实验结果相关修改均由本地 Agent 完成。":"The top image is compiled by the current LaTeX; initial draft and experiment result related edits are performed by the local Agent."
  ,"高级：生成新的表格初稿":"Advanced: generate a new table draft"
  ,"初始表格规格":"Initial table specification"
  ,"列: Method | Dataset A metric | Dataset B metric\n行: source\nCaption: Main comparison.\n字号: small\n最优值: max":"Column: Method | Dataset A metric | Dataset B metric\nLine: source\nCaption: Main comparison.\nFont size: small\nBest value: max."
  ,"本地 Agent 生成初稿":"Local agent generated the first draft."
  ,"可编辑 Table LaTeX":"Editable Table LaTeX."
  ,"保存修改":"Save changes"
  ,"关闭清空确认":"Close and clear confirmation."
  ,"这会删除当前项目的生成正文、候选、对话和图表产物，但保留配置、输入与实验结果。":"This will delete the generated main text content candidates dialogues and chart artifacts for the current project, while preserving configuration inputs and experimental results."
  ,"当前项目 ID（可选择复制）":"Current project ID (copyable)."
  ,"复制 ID":"Copy ID."
  ,"粘贴或输入项目 ID 以确认":"Paste or enter the project ID to confirm."
  ,"取消":"cancel"
  ,"确认清空":"Confirm clear"
  ,"关闭安全密钥输入":"Disable security key input"
  ,"密钥只写入当前 Paper Studio 进程内存，不进入聊天记录、浏览器存储或项目文件。":"Keys are written only to the current Paper Studio process memory and are not stored in chat history browser storage or project files."
  ,"服务商":"Service provider"
  ,"安全更新":"Security update"
}));

function translateStudioText(value) {
  const exact = studioTranslations.get(value);
  if (exact) return exact;
  const replacements = [
    ["参考论文：", "Reference paper: "],
    ["正文已全部写入 LaTeX；请在图表工作台完成并确认：", "All prose has been written to LaTeX; complete and approve these artifacts in the figure and table workspace: "],
    ["第 ", "Page "],
    [" 页", ""],
    [" · 图", " · Figures"],
    [" · 表", " · Tables"],
    ["已等待 ", "waited "],
    [" 秒", " seconds"],
    [" 后", " after"],
  ];
  let translated = value;
  replacements.forEach(([source, target]) => { translated = translated.split(source).join(target); });
  translated = translated
    .replace(/^正在生成 (.+)$/, "Generating $1")
    .replace(/^已写入并编译 (.+)$/, "Written and compiled: $1")
    .replace(/^(.+) 的正文已写入 LaTeX 和 PDF，计划图表已以 placeholder 保留。$/, "$1 prose was written to LaTeX and PDF; planned figures and tables remain as placeholders.")
    .replace(/^(.+) 的新版本已替换写入 LaTeX，并完成 PDF 编译。$/, "The new version of $1 was written to LaTeX and the PDF was compiled.")
    .replace(/^\u5168\u90e8 (\d+) \u4e2a\u6bb5\u843d\u5df2\u7ecf\u5199\u5165 LaTeX\uff0c\u53ef\u7ee7\u7eed\u9010\u6bb5\u4fee\u6539\u3002$/, "All $1 paragraphs have been written to LaTeX and remain editable.")
    .replace(/^\u5c06\u6309\u9879\u76ee\u5199\u4f5c\u987a\u5e8f\u8865\u9f50 (\d+) \/ (\d+) \u4e2a\u672a\u5b8c\u6210\u6bb5\u843d\uff1b\u5df2\u63a5\u53d7\u5185\u5bb9\u4e0d\u4f1a\u88ab\u8986\u76d6\u3002$/, "Draft $1 of $2 unfinished paragraphs in project order; accepted content will not be overwritten.")
    .replace(/^\u4e00\u952e\u751f\u6210\u5f53\u524d Section\uff08(\d+) \u6bb5\u5f85\u5b8c\u6210\uff09$/, "Generate current section ($1 paragraphs remaining)")
    .replace(/^\u5df2\u4ece PDF \u8fd4\u56de (.+) \u7684\u6587\u5b57\u7f16\u8f91\u4f4d\u7f6e\u3002$/, "Returned from the PDF to the text editor for $1.")
    .replace(/^\u5df2\u4ece PDF \u8fd4\u56de (.+) \u7684(\u8868\u683c|\u56fe\u7247)\u7f16\u8f91\u4f4d\u7f6e\u3002$/, (_, id, kind) => `Returned from the PDF to the ${kind === "\u8868\u683c" ? "table" : "figure"} editor for ${id}.`)
    .replace(/^(.+) \u7684\u5f53\u524d\u6bb5\u843d\u5df2\u751f\u6210\u5e76\u4fdd\u5b58\u3002$/, "The current paragraph in $1 was generated and saved.")
    .replace(/^(.+) \u5df2\u63a5\u53d7\u5e76\u5b8c\u6210 LaTeX \u7f16\u8bd1\uff1b\u5f53\u524d section \u5df2\u5b8c\u6210\u3002$/, "$1 was accepted and compiled; the current section is complete.")
    .replace(/^(.+) \u5df2\u63a5\u53d7\u5e76\u5b8c\u6210 LaTeX \u7f16\u8bd1\uff1b\u6b63\u5728\u540e\u53f0\u51c6\u5907 (.+) \u5019\u9009\u3002$/, "$1 was accepted and compiled; the candidate for $2 is being prepared in the background.")
    .replace(/^(.+) \u5df2\u63a5\u53d7\u5e76\u5b8c\u6210 LaTeX \u7f16\u8bd1\uff1b(.+) \u5019\u9009\u5df2\u5237\u65b0\u3002$/, "$1 was accepted and compiled; the candidate for $2 was refreshed.")
    .replace(/^(.+) \u5df2\u63a5\u53d7\u5e76\u5b8c\u6210 LaTeX \u7f16\u8bd1\u3002$/, "$1 was accepted and compiled in LaTeX.")
    .replace(/^(.+) \u5df2\u52a0\u5165\u961f\u5217\uff1b\u5f53\u524d\u6bb5\u843d\u751f\u6210\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u5f00\u59cb\u6574\u8282\u751f\u6210\u3002$/, "$1 was queued and will start after the current paragraph finishes.")
    .replace(/^(.+) \u7684\u6574\u8282\u751f\u6210\u4efb\u52a1\u5df2\u542f\u52a8\uff1b\u5c06\u6309\u6bb5\u843d\u987a\u5e8f\u81ea\u52a8\u5199\u5165 LaTeX \u5e76\u7f16\u8bd1\u3002$/, "Full-section drafting for $1 has started and will write paragraphs to LaTeX in order.")
    .replace(/\uff08([^\uff09]+)\uff09/g, " ($1)");
  return translated;
}

function translateStudioUi(root = document.body) {
  document.documentElement.lang = studioUiLanguage === "en" ? "en" : "zh-CN";
  const select = $("studio-language-select");
  if (select) select.value = studioUiLanguage;
  if (studioUiLanguage !== "en" || !root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(node => {
    if (node.parentElement?.closest("script,style,textarea,code")) return;
    if (node.parentElement?.closest("pre") && !node.parentElement.closest("pre.message")) return;
    const value = node.nodeValue.trim();
    const translated = translateStudioText(value);
    if (translated !== value) node.nodeValue = node.nodeValue.replace(value, translated);
  });
  root.querySelectorAll?.("[placeholder]").forEach(node => {
    const translated = studioTranslations.get(node.placeholder);
    if (translated) node.placeholder = translated;
  });
}

translateStudioUi();
$("studio-language-select")?.addEventListener("change", event => {
  const language = event.target.value === "en" ? "en" : "zh";
  localStorage.setItem("research-avatar-language", language);
  if (window.parent !== window) {
    window.parent.postMessage({type: "research-avatar-language", language}, window.location.origin);
  }
  const url = new URL(window.location.href);
  url.searchParams.set("lang", language);
  window.location.replace(url.toString());
});
new MutationObserver(records => records.forEach(record => {
  if (record.type === "characterData") translateStudioUi(record.target.parentElement);
  record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) translateStudioUi(node);
    if (node.nodeType === Node.TEXT_NODE) translateStudioUi(node.parentElement);
  });
})).observe(document.body, {subtree:true, childList:true, characterData:true});
const STUDIO_BASE_PATH = ["/demo-studio", "/paper-studio"].find(
  prefix => window.location.pathname === prefix
    || window.location.pathname.startsWith(prefix + "/"),
) || "";

function studioPath(path) {
  const value = String(path || "");
  if (!STUDIO_BASE_PATH || !value.startsWith("/") || value.startsWith("//")) return value;
  if (value === STUDIO_BASE_PATH || value.startsWith(STUDIO_BASE_PATH + "/")) return value;
  return STUDIO_BASE_PATH + value;
}

function normalizeStateUrls(value, key = "") {
  if (Array.isArray(value)) return value.map((item) => normalizeStateUrls(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([childKey, child]) => [
        childKey,
        normalizeStateUrls(child, childKey),
      ]),
    );
  }
  const urlLikeKey = key.endsWith("_url")
    || ["pdf", "png", "pptx", "preview", "draft"].includes(key);
  return typeof value === "string" && urlLikeKey ? studioPath(value) : value;
}
const ACTIVE_FIGURE_KEY = "paper-studio.active-figure";
const PDF_NAVIGATION_KEY = "paper-studio.pdf-navigation-visible";
const CAPTION_DRAFTS_KEY_PREFIX = "paper-studio.caption-drafts.";
const FIGURE_EDITOR_DRAFTS_KEY_PREFIX = "paper-studio.figure-editor-drafts.";
const PROSE_DRAFTS_KEY_PREFIX = "paper-studio.prose-drafts.";
const TITLE_DRAFTS_KEY_PREFIX = "paper-studio.title-drafts.";
const COMMENT_DRAFTS_KEY_PREFIX = "paper-studio.comment-drafts.";
const LEGACY_DRAFT_KEY_PREFIXES = [
  "paperstudio.caption-drafts.",
  "paperstudio.figure-editor-drafts.",
  "paperstudio.prose-drafts.",
  "paperstudio.title-drafts.",
  "paperstudio.comment-drafts.",
];
let state = null;
let pdfNavigationVisible = (() => {
  try {
    return localStorage.getItem(PDF_NAVIGATION_KEY) === "true";
  } catch (_error) {
    return false;
  }
})();
let activeView = (() => {
  const requested = new URLSearchParams(window.location.search).get("view");
  if (["writing", "figures", "tables"].includes(requested)) return requested;
  return "writing";
})();
let activeSection = (() => {
  const requested = new URLSearchParams(window.location.search).get("section");
  if (requested) return requested;
  return "abstract";
})();
let activeFigure = (() => {
  try {
    return localStorage.getItem(ACTIVE_FIGURE_KEY) || "";
  } catch (_error) {
    return "";
  }
})();
const autoAttempted = new Set();
const autoFigurePromptAttempted = new Set();
const autoDataPanelAttempted = new Set();
const autoTableGenerateAttempted = new Set();
let figurePollTimer = null;
let fullDraftPollTimer = null;
let titleBusy = false;
let acceptRequestBusy = false;
let proseRequestBusy = false;
let paragraphRequestBusy = false;
let compileRequestBusy = false;
let modelApplyBusy = false;
let figureRequestBusy = false;
let generatedResetBusy = false;
let fullDraftRequestBusy = false;
let queuedSectionDraftStart = "";
let pdfLocateRequestId = 0;
let pdfResizeObserver = null;
let proseBaselineKey = "";
let proseBaselineText = "";
const mechanismPreviewModes = new Map();
const captionDrafts = new Map();
let captionDraftProjectId = "";
const figureEditorDrafts = new Map();
let figureEditorDraftProjectId = "";
const proseDrafts = new Map();
let proseDraftProjectId = "";
const titleDrafts = new Map();
let titleDraftProjectId = "";
const commentDrafts = new Map();
let commentDraftProjectId = "";

function syncCaptionDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === captionDraftProjectId) return;
  captionDraftProjectId = projectId;
  captionDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(CAPTION_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([figureId, value]) => {
      if (typeof value === "string") {
        // Legacy drafts predate generation-version tracking. Treat them as
        // older than any server-generated caption.
        captionDrafts.set(figureId, {value, generatedAt: ""});
      } else if (value && typeof value.value === "string") {
        captionDrafts.set(figureId, {
          value: value.value,
          generatedAt: String(value.generatedAt || ""),
        });
      }
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistCaptionDrafts() {
  if (!captionDraftProjectId) return;
  try {
    localStorage.setItem(
      CAPTION_DRAFTS_KEY_PREFIX + captionDraftProjectId,
      JSON.stringify(Object.fromEntries(captionDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberCaptionDraft(figureId, caption) {
  syncCaptionDraftProject();
  const figure = state && (state.figures || []).find((item) => item.id === figureId);
  captionDrafts.set(figureId, {
    value: caption,
    generatedAt: String((figure && figure.caption_generated_at) || ""),
  });
  persistCaptionDrafts();
}

function forgetCaptionDraft(figureId) {
  syncCaptionDraftProject();
  captionDrafts.delete(figureId);
  persistCaptionDrafts();
}

function syncFigureEditorDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === figureEditorDraftProjectId) return;
  figureEditorDraftProjectId = projectId;
  figureEditorDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(FIGURE_EDITOR_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([figureId, fields]) => {
      if (fields && typeof fields === "object" && !Array.isArray(fields)) {
        figureEditorDrafts.set(figureId, fields);
      }
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistFigureEditorDrafts() {
  if (!figureEditorDraftProjectId) return;
  try {
    localStorage.setItem(
      FIGURE_EDITOR_DRAFTS_KEY_PREFIX + figureEditorDraftProjectId,
      JSON.stringify(Object.fromEntries(figureEditorDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function figureEditorDraft(figureId, field) {
  syncFigureEditorDraftProject();
  const fields = figureEditorDrafts.get(figureId);
  return fields && Object.prototype.hasOwnProperty.call(fields, field)
    ? fields[field]
    : undefined;
}

function rememberFigureEditorDraft(figureId, field, value, canonicalValue = "") {
  syncFigureEditorDraftProject();
  const canonical = String(canonicalValue || "");
  if (value === canonical) {
    forgetFigureEditorDraft(figureId, field);
    return;
  }
  const fields = {...(figureEditorDrafts.get(figureId) || {})};
  fields[field] = value;
  figureEditorDrafts.set(figureId, fields);
  persistFigureEditorDrafts();
}

function forgetFigureEditorDraft(figureId, field) {
  syncFigureEditorDraftProject();
  const fields = {...(figureEditorDrafts.get(figureId) || {})};
  delete fields[field];
  if (Object.keys(fields).length) figureEditorDrafts.set(figureId, fields);
  else figureEditorDrafts.delete(figureId);
  persistFigureEditorDrafts();
}

function renderFigureEditorInput(input, figureId, field, canonicalValue = "") {
  const canonical = String(canonicalValue || "");
  let draft = figureEditorDraft(figureId, field);
  if (draft === canonical) {
    forgetFigureEditorDraft(figureId, field);
    draft = undefined;
  }
  if (draft === undefined && input.value === canonical) {
    input.dataset.dirty = "false";
  }
  const changedFigure = input.dataset.figureId !== figureId;
  if (changedFigure || (input.dataset.dirty !== "true" && document.activeElement !== input)) {
    input.value = draft !== undefined ? draft : canonical;
    input.dataset.figureId = figureId;
    input.dataset.dirty = String(draft !== undefined);
  }
}

function syncProseDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === proseDraftProjectId) return;
  proseDraftProjectId = projectId;
  proseDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(PROSE_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([editorKey, draft]) => {
      if (draft && typeof draft.value === "string" && typeof draft.baseline === "string") {
        proseDrafts.set(editorKey, draft);
      }
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistProseDrafts() {
  if (!proseDraftProjectId) return;
  try {
    localStorage.setItem(
      PROSE_DRAFTS_KEY_PREFIX + proseDraftProjectId,
      JSON.stringify(Object.fromEntries(proseDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberProseDraft(editorKey, value, baseline) {
  syncProseDraftProject();
  if (value === baseline) {
    forgetProseDraft(editorKey);
    return;
  }
  proseDrafts.set(editorKey, {value, baseline});
  persistProseDrafts();
}

function forgetProseDraft(editorKey) {
  syncProseDraftProject();
  proseDrafts.delete(editorKey);
  persistProseDrafts();
}

function syncTitleDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === titleDraftProjectId) return;
  titleDraftProjectId = projectId;
  titleDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(TITLE_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([field, value]) => {
      if (typeof value === "string") titleDrafts.set(field, value);
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistTitleDrafts() {
  if (!titleDraftProjectId) return;
  try {
    localStorage.setItem(
      TITLE_DRAFTS_KEY_PREFIX + titleDraftProjectId,
      JSON.stringify(Object.fromEntries(titleDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberTitleDraft(field, value, canonicalValue = "") {
  syncTitleDraftProject();
  if (value === canonicalValue) titleDrafts.delete(field);
  else titleDrafts.set(field, value);
  persistTitleDrafts();
}

function forgetTitleDraft(field) {
  syncTitleDraftProject();
  titleDrafts.delete(field);
  persistTitleDrafts();
}

function renderTitleDraftInput(input, field, canonicalValue, force = false) {
  let draft = titleDrafts.get(field);
  if (draft === canonicalValue) {
    forgetTitleDraft(field);
    draft = undefined;
  }
  if (force || (input.dataset.dirty !== "true" && document.activeElement !== input)) {
    input.value = draft !== undefined ? draft : canonicalValue;
    input.dataset.dirty = String(draft !== undefined);
  }
}

function syncCommentDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === commentDraftProjectId) return;
  commentDraftProjectId = projectId;
  commentDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(COMMENT_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([editorKey, value]) => {
      if (typeof value === "string" && value) commentDrafts.set(editorKey, value);
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistCommentDrafts() {
  if (!commentDraftProjectId) return;
  try {
    localStorage.setItem(
      COMMENT_DRAFTS_KEY_PREFIX + commentDraftProjectId,
      JSON.stringify(Object.fromEntries(commentDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberCommentDraft(editorKey, value) {
  syncCommentDraftProject();
  if (value) commentDrafts.set(editorKey, value);
  else commentDrafts.delete(editorKey);
  persistCommentDrafts();
}

function forgetCommentDraft(editorKey) {
  syncCommentDraftProject();
  commentDrafts.delete(editorKey);
  persistCommentDrafts();
}

function clearBrowserDraftsForProject(projectId) {
  if (!projectId) return;
  captionDrafts.clear();
  figureEditorDrafts.clear();
  proseDrafts.clear();
  titleDrafts.clear();
  commentDrafts.clear();
  mechanismPreviewModes.clear();
  proseBaselineKey = "";
  proseBaselineText = "";
  [
    CAPTION_DRAFTS_KEY_PREFIX,
    FIGURE_EDITOR_DRAFTS_KEY_PREFIX,
    PROSE_DRAFTS_KEY_PREFIX,
    TITLE_DRAFTS_KEY_PREFIX,
    COMMENT_DRAFTS_KEY_PREFIX,
    ...LEGACY_DRAFT_KEY_PREFIXES,
  ].forEach((prefix) => {
    try {
      localStorage.removeItem(prefix + projectId);
    } catch (_error) {
      // Storage can be unavailable in strict browser privacy modes.
    }
  });
}

function uniqueArtifacts(artifacts = []) {
  const seen = new Set();
  return artifacts.filter((artifact) => {
    if (!artifact.id || seen.has(artifact.id)) return false;
    seen.add(artifact.id);
    return true;
  });
}

// POST-shaped but read-only: the gateway lets these through on a demo
// session too (see DEMO_SAFE_WRITE_PATHS in online_studio/server.py).
const DEMO_SAFE_WRITE_PATHS = new Set(["/api/pdf/locate", "/api/select-paragraph"]);

async function request(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  // The gateway already refuses every other non-GET/HEAD request against a
  // demo session unconditionally; applyReadOnlyDemoRestrictions() keeps
  // every mutating control disabled so this should be unreachable in
  // normal use. This stays only as a defensive fallback -- no dialog to
  // redirect into.
  if (
    state
    && state.demo_mode
    && !["GET", "HEAD"].includes(method)
    && !DEMO_SAFE_WRITE_PATHS.has(path)
  ) {
    throw new Error(studioT("这是只读 Demo，无法生成或修改内容。", "This is a read only demo; cannot generate or modify content."));
  }
  const response = await fetch(studioPath(path), {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const payload = await response.json().catch(() => ({error: response.statusText}));
  if (!response.ok || payload.ok === false) throw new Error(payload.error || payload.message || response.statusText);
  return normalizeStateUrls(payload);
}

function updateAcceptButton() {
  const section = state && state.sections && state.sections[activeSection];
  const planningOnly = Boolean(section && section.writing_mode === "plan_only");
  const paragraph = section && section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  const accepted = paragraph && paragraph.accepted_text;
  const visibleText = $("candidate").value.trim();
  const manualRevision = visibleText !== proseBaselineText.trim();
  const canAccept = !planningOnly && Boolean(visibleText) && Boolean(candidate || manualRevision);
  $("accept").disabled = !canAccept;
  $("accept").textContent = canAccept
    ? "Accept → LaTeX"
    : accepted
      ? studioT("已写入 LaTeX", "LaTeX has been written.")
      : studioT("等待 candidate", "Waiting for candidate.");
  $("accept").title = accepted && !canAccept
    ? studioT("当前版本已写入 LaTeX；可直接修改正文，或填写 comment 让写作模型生成新 candidate。", "The current version is written in LaTeX; you can modify the main text directly or give the writing model feedback to generate a new candidate.")
    : "";
}

function setBusy(busy, label = "") {
  const planningOnly = Boolean(
    state && state.sections && state.sections[activeSection]
    && state.sections[activeSection].writing_mode === "plan_only"
  );
  $("generate").disabled = busy || planningOnly;
  $("compile").disabled = busy;
  $("candidate").disabled = busy || planningOnly;
  $("comment").disabled = busy || planningOnly;
  $("model").disabled = busy;
  $("model-apply").disabled = busy;
  if (busy) {
    $("accept").disabled = true;
    const paragraph = state && state.sections && state.sections[activeSection]
      ? state.sections[activeSection].current_paragraph
      : null;
    if (paragraph && !$("candidate").value) {
      $("candidate").placeholder = studioT("正在结合已批准的段落结构、working abstract 和实验结果生成当前段落…", "Currently combining approved paragraph structure working abstract and experimental results to generate the current paragraph.");
    }
    $("message").textContent = label || "Working…";
  } else {
    updateAcceptButton();
    updateModelApplyButton();
  }
  document.querySelectorAll(".section-button").forEach((button) => {
    button.disabled = busy;
  });
  document.querySelectorAll(".paragraph-nav button").forEach((button) => {
    button.disabled = busy;
  });
  if (busy) {
    document.querySelectorAll(".figure-card, .figure-actions button").forEach((button) => {
      button.disabled = true;
    });
    $("figure-placement").disabled = true;
  } else if (["figures", "tables"].includes(activeView) && state) {
    document.querySelectorAll(".figure-card").forEach((button) => {
      button.disabled = false;
    });
    updateFigureButtonStates();
  }
}

function updateModelApplyButton() {
  const visibleModel = $("model").value.trim();
  $("model-apply").disabled = modelApplyBusy
    || proseRequestBusy
    || fullDraftRequestBusy
    || titleBusy
    || !visibleModel
    || visibleModel === String((state && state.model) || "gpt-5-nano");
}

function showMessage(message, error = false) {
  $("message").textContent = message || "";
  $("message").classList.toggle("error", error);
}

function updateTitleSaveButton() {
  const editor = (state && state.title_editor) || {};
  const visibleTitle = $("paper-title").value.replace(/\s+/g, " ").trim();
  const currentTitle = String(editor.current_title || "").replace(/\s+/g, " ").trim();
  const changed = Boolean(visibleTitle) && visibleTitle !== currentTitle;
  $("title-save").disabled = titleBusy || !changed;
  $("title-save").textContent = changed ? studioT("确认写入 LaTeX", "Confirm writing to LaTeX") : studioT("已写入 PDF", "Written to PDF");
  $("title-save").title = changed ? studioT("确认后更新 LaTeX 并重新编译 PDF。", "Update LaTeX after confirmation and recompile the PDF.") : studioT("当前标题已经写入 PDF。", "The current title has been written into the PDF.");
  if (!changed && !state?.pdf?.exists) {
    $("title-save").textContent = studioT("当前标题", "Current title");
    $("title-save").title = studioT("标题已保存在稿件中；编译论文后才会生成 PDF。", "The title is saved in the manuscript; compile the paper to create a PDF.");
  }
}

function setTitleBusy(busy, message = "") {
  titleBusy = busy;
  $("title-generate").disabled = busy;
  $("paper-title").disabled = busy;
  $("title-gpt-prompt").disabled = busy;
  if (busy) {
    $("title-save").disabled = true;
  } else {
    updateTitleSaveButton();
  }
  if (message) {
    $("title-status").textContent = message;
    $("title-status").classList.remove("error");
  }
}

function renderTitleEditor(force = false) {
  const editor = state.title_editor || {};
  const titleInput = $("paper-title");
  const promptInput = $("title-gpt-prompt");
  titleInput.disabled = titleBusy;
  promptInput.disabled = titleBusy;
  $("title-current-summary").textContent = editor.current_title || studioT("未找到标题", "Title not found.");
  renderTitleDraftInput(titleInput, "title", editor.candidate || editor.current_title || "", force);
  renderTitleDraftInput(promptInput, "prompt", editor.prompt || "", force);
  $("title-status").textContent = editor.last_message || (
    editor.candidate ? studioT("模型 candidate 尚未保存；可编辑后确认。", "Model candidate not saved yet; it can be edited and confirmed.") : studioT("修改后需确认，才会写入 LaTeX。", "Must confirm after modification before writing to LaTeX.")
  );
  $("title-status").classList.remove("error");
  if (!titleBusy) $("title-generate").disabled = false;
  updateTitleSaveButton();
}

function renderSections() {
  const root = $("sections");
  root.innerHTML = "";
  Object.entries(state.sections).forEach(([key, section]) => {
    const button = document.createElement("button");
    button.className = "section-button" + (key === activeSection ? " active" : "");
    const dot = section.conversation_active ? "active" : "";
    button.textContent = section.title;
    const indicator = document.createElement("span");
    indicator.className = `dot ${dot}`;
    button.appendChild(indicator);
    button.onclick = () => {
      activeSection = key;
      activeView = "writing";
      render();
    };
    root.appendChild(button);
  });
}

function renderParagraphNavigation(section) {
  const root = $("paragraph-nav");
  root.innerHTML = "";
  (section.paragraph_navigation || []).forEach((paragraph) => {
    const button = document.createElement("button");
    button.textContent = paragraph.id;
    const artifacts = uniqueArtifacts(paragraph.artifacts || []);
    const visibleArtifacts = artifacts;
    if (visibleArtifacts.length) {
      const badge = document.createElement("span");
      badge.className = "nav-artifact";
      badge.textContent = `◆${visibleArtifacts.map((item) => item.id).join("/")}`;
      button.appendChild(badge);
    }
    button.title = `${paragraph.status}: ${paragraph.purpose}${artifacts.length ? ` · association ${artifacts.map((item) => item.id).join(", ")}` : ""}`;
    button.className = `${paragraph.status}${paragraph.selected ? " selected" : ""}${visibleArtifacts.length ? " has-artifact" : ""}`;
    button.dataset.paragraphId = paragraph.id;
    button.disabled = false;
    button.onclick = async () => {
      if (paragraph.selected || paragraphRequestBusy) return;
      paragraphRequestBusy = true;
      const requestedSection = activeSection;
      try {
        setBusy(true, studioT(`正在切换到 ${paragraph.id}…`, `Switching to. ${paragraph.id}…`));
        const payload = await request("/api/select-paragraph", {
          method: "POST",
          body: JSON.stringify({
            section: requestedSection,
            paragraph_id: paragraph.id,
          }),
        });
        state = payload.state;
        if (activeSection === requestedSection) {
          render();
          showMessage(
            paragraph.status === "accepted"
              ? studioT(`已切换到 ${paragraph.id}；可基于已接受版本继续修改。`, `Switched to ${paragraph.id}; Can continue editing based on the accepted version.`)
              : studioT(`已切换到 ${paragraph.id}。`, `Switched to ${paragraph.id}.`),
          );
        } else {
          renderSections();
        }
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        paragraphRequestBusy = false;
        setBusy(false);
      }
    };
    root.appendChild(button);
  });
}

function renderReferenceContext(section) {
  const card = $("reference-context-card");
  const context = section.reference_context || {};
  const excerpts = Array.isArray(context.excerpts) ? context.excerpts : [];
  const constraints = Array.isArray(context.writing_constraints) ? context.writing_constraints : [];
  const abstracted = context.mode === "abstracted";
  if (!context.source_heading || !context.logic_summary_zh || (!excerpts.length && !constraints.length)) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  $("reference-context-title").textContent = abstracted
    ? studioT("提炼后的参考结构", "Refined reference structure")
    : studioT("参考论文中对应的写法", "The corresponding formulation in the reference papers.");
  const toggle = $("reference-excerpts-toggle");
  toggle.hidden = abstracted;
  $("reference-excerpts-title").textContent = abstracted ? "" : studioT("查看参考原文", "View referenced original text.");
  const root = $("reference-context-excerpts");
  root.replaceChildren(...excerpts.map((excerpt) => {
    const container = document.createElement("div");
    container.className = "reference-excerpt";
    const quote = document.createElement("blockquote");
    quote.textContent = excerpt.text || "";
    container.append(quote);
    return container;
  }));
}

function renderStructureBlueprint(section) {
  const root = $("structure-blueprint");
  root.innerHTML = "";
  (section.structure_blueprint || []).forEach((paragraph) => {
    const row = document.createElement("div");
    row.className = `structure-row${section.current_paragraph && section.current_paragraph.id === paragraph.id ? " active" : ""}`;
    const id = document.createElement("span");
    id.textContent = paragraph.id;
    const content = document.createElement("span");
    content.textContent = paragraph.purpose;
    row.append(id, content);
    root.appendChild(row);
  });
}

function capturePdfPosition(pages) {
  const pageElements = [...pages.querySelectorAll(".pdf-page")];
  if (!pageElements.length || !pages.clientHeight) return null;
  const center = pages.getBoundingClientRect().top + pages.clientTop + pages.clientHeight / 2;
  const page = pageElements.find((item) => (
    center >= item.getBoundingClientRect().top && center <= item.getBoundingClientRect().bottom
  )) || pageElements.reduce((closest, item) => (
    Math.abs(item.getBoundingClientRect().top + item.offsetHeight / 2 - center)
      < Math.abs(closest.getBoundingClientRect().top + closest.offsetHeight / 2 - center)
      ? item
      : closest
  ));
  return {
    page: page.dataset.page,
    ratio: page.offsetHeight
      ? (center - page.getBoundingClientRect().top) / page.offsetHeight
      : 0,
  };
}

function restorePdfPosition(pages, position) {
  if (!position) return;
  requestAnimationFrame(() => {
    const page = pages.querySelector(`[data-page="${position.page}"]`);
    if (!page) return;
    const top = page.getBoundingClientRect().top - pages.getBoundingClientRect().top
      - pages.clientTop + pages.scrollTop;
    const center = top + position.ratio * page.offsetHeight;
    pages.scrollTop = Math.max(0, center - pages.clientHeight / 2);
    updatePdfPageIndicator();
  });
}

function updatePdfPageIndicator() {
  const pages = $("pdf-pages");
  const indicator = $("pdf-page-indicator");
  const position = capturePdfPosition(pages);
  const total = Number(state && state.pdf && state.pdf.page_count) || 0;
  const budget = state && state.pdf && state.pdf.page_budget;
  const budgetText = budget && budget.limit && budget.content_pages
    ? ` · ${studioT("正文", "Body")} ${budget.content_pages}/${budget.limit}`
    : "";
  indicator.textContent = position && total
    ? `${studioT("第", "Page")} ${position.page} / ${total}${studioT(" 页", "")}${budgetText}`
    : studioT("第 — / — 页", "Page — / —");
  $("pdf-navigation").querySelectorAll(".pdf-thumbnail").forEach((thumbnail) => {
    thumbnail.classList.toggle("active", thumbnail.dataset.page === (position && position.page));
  });
}

function renderPdf() {
  const viewer = $("pdf-viewer");
  const pages = $("pdf-pages");
  const navigationRoot = $("pdf-navigation");
  const empty = $("pdf-empty");
  const toggle = $("pdf-navigation-toggle");
  const download = $("pdf-download");
  toggle.textContent = pdfNavigationVisible ? studioT("隐藏导航栏", "Hide navigation bar.") : studioT("显示导航栏", "Show navigation bar.");
  toggle.setAttribute("aria-pressed", pdfNavigationVisible ? "true" : "false");
  if (state.pdf.exists) {
    download.hidden = false;
    download.href = studioPath(state.pdf.url || "/paper.pdf");
    download.download = `${String(state.project && state.project.id || "paper").replace(/[^A-Za-z0-9._-]+/g, "-")}.pdf`;
    viewer.hidden = false;
    viewer.classList.toggle("navigation-visible", pdfNavigationVisible);
    empty.hidden = true;
    const signature = `${state.pdf.version}:${state.pdf.page_count}`;
    if (pages.dataset.signature !== signature) {
      const previousPosition = capturePdfPosition(pages);
      pages.replaceChildren();
      for (let pageNumber = 1; pageNumber <= state.pdf.page_count; pageNumber += 1) {
        const page = document.createElement("div");
        page.className = "pdf-page";
        page.dataset.page = String(pageNumber);
        page.title = studioT("双击正文、图片或表格，返回对应编辑位置", "Double-click the body text, image, or table to jump to the corresponding editing position.");
        const image = document.createElement("img");
        image.alt = studioT(`论文 PDF 第 ${pageNumber} 页`, `Paper PDF page ${pageNumber} page`);
        image.draggable = false;
        image.width = Number(state.pdf.page_width_pt) || 612;
        image.height = Number(state.pdf.page_height_pt) || 792;
        image.onload = updatePdfPageIndicator;
        image.src = studioPath(`/paper-page/${pageNumber}.svg?v=${state.pdf.version}`);
        page.appendChild(image);
        page.ondblclick = (event) => locatePdfEditTarget(event, page);
        pages.appendChild(page);
      }
      pages.dataset.signature = signature;
      restorePdfPosition(pages, previousPosition);
    }
    if (pdfNavigationVisible && navigationRoot.dataset.signature !== signature) {
      navigationRoot.replaceChildren();
      for (let pageNumber = 1; pageNumber <= state.pdf.page_count; pageNumber += 1) {
        const thumbnail = document.createElement("button");
        thumbnail.className = "pdf-thumbnail";
        thumbnail.type = "button";
        thumbnail.dataset.page = String(pageNumber);
        thumbnail.title = studioT(`转到第 ${pageNumber} 页`, `Go to the ${pageNumber} page`);
        const image = document.createElement("img");
        image.alt = studioT(`第 ${pageNumber} 页`, `the ${pageNumber} page`);
        image.src = studioPath(`/paper-page/${pageNumber}.svg?v=${state.pdf.version}`);
        thumbnail.appendChild(image);
        thumbnail.onclick = () => {
          const target = pages.querySelector(`[data-page="${pageNumber}"]`);
          if (target) pages.scrollTo({
            top: pages.scrollTop + target.getBoundingClientRect().top
              - pages.getBoundingClientRect().top - pages.clientTop,
            behavior: "smooth",
          });
        };
        navigationRoot.appendChild(thumbnail);
      }
      navigationRoot.dataset.signature = signature;
    }
    pages.onscroll = updatePdfPageIndicator;
    if (!pdfResizeObserver) {
      pdfResizeObserver = new ResizeObserver(updatePdfPageIndicator);
      pdfResizeObserver.observe(pages);
    }
    requestAnimationFrame(updatePdfPageIndicator);
  } else {
    download.hidden = true;
    viewer.hidden = true;
    empty.hidden = false;
    updatePdfPageIndicator();
  }
  const compile = state.compile || {};
  $("compile-status").textContent = compile.status || "not_run";
  $("compile-status").className = "status " + (compile.status === "ok" ? "ok" : compile.status === "failed" ? "warn" : "");
}

async function locatePdfEditTarget(event, pageElement) {
  const locateRequestId = ++pdfLocateRequestId;
  const rectangle = pageElement.getBoundingClientRect();
  if (!rectangle.width || !rectangle.height) return;
  const page = Number(pageElement.dataset.page);
  const x = (event.clientX - rectangle.left) / rectangle.width * state.pdf.page_width_pt;
  const y = (event.clientY - rectangle.top) / rectangle.height * state.pdf.page_height_pt;
  try {
    showMessage(studioT("正在定位 PDF 中的源内容…", "Locating source content in PDF…"));
    const payload = await request("/api/pdf/locate", {
      method: "POST",
      body: JSON.stringify({page, x, y}),
    });
    if (locateRequestId !== pdfLocateRequestId) return;
    const target = payload.target;
    activeSection = target.section;
    activeView = target.view;
    if (target.view === "writing") {
      const selected = await request("/api/select-paragraph", {
        method: "POST",
        body: JSON.stringify({
          section: target.section,
          paragraph_id: target.paragraph_id,
        }),
      });
      if (locateRequestId !== pdfLocateRequestId) return;
      state = selected.state;
      render();
      showMessage(studioT(`已从 PDF 返回 ${target.paragraph_id} 的文字编辑位置。`, `Returned from PDF ${target.paragraph_id} The text editing position.`));
      return;
    }
    activeFigure = target.artifact_id;
    try {
      localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
    } catch (_error) {}
    render();
    $("figure-message").textContent = studioT(`已从 PDF 返回 ${target.artifact_id} 的${target.view === "tables" ? "表格" : "图片"}编辑位置。`, `Returned from PDF ${target.artifact_id} of${target.view === "tables" ? "table" : "Image"}Edit position.`);
  } catch (error) {
    if (locateRequestId !== pdfLocateRequestId) return;
    showMessage(error.message, true);
  }
}

$("pdf-navigation-toggle").onclick = () => {
  pdfNavigationVisible = !pdfNavigationVisible;
  try {
    localStorage.setItem(PDF_NAVIGATION_KEY, String(pdfNavigationVisible));
  } catch (_error) {}
  renderPdf();
};

function sectionFigures() {
  const paragraph = state.sections[activeSection].current_paragraph;
  const relatedIds = new Set(
    (paragraph && paragraph.artifacts || [])
      .filter((artifact) => activeView === "tables" ? artifact.kind === "table" : artifact.kind === "figure")
      .map((artifact) => artifact.id),
  );
  const collection = activeView === "tables" ? (state.tables || []) : (state.figures || []);
  return collection.filter((artifact) =>
    (artifact.source_sections || []).includes(activeSection)
    || (artifact.related_paragraphs && artifact.related_paragraphs[activeSection])
    || relatedIds.has(artifact.id)
  );
}

function selectedFigure() {
  const figures = sectionFigures();
  return figures.find((figure) => figure.id === activeFigure) || figures[0];
}

function figureIsRunning(figure) {
  return ["prompt_generating", "image_generating", "agent_generating", "agent_editing"].includes(figure.status);
}

function updateMechanismFlow(figure) {
  if (!figure || figure.kind !== "mechanism") return;
  const promptReady = Boolean(String(figure.draw_prompt || "").trim());
  const imageReady = Boolean(
    figure.paper_preview_url
    || ["agent_generating", "built", "approved"].includes(figure.status)
  );
  const paperReady = Boolean(
    figure.paper_preview_url
    || ((figure.downloads || {}).pdf && (figure.downloads || {}).pptx)
  );
  const promptActive = figure.status === "prompt_generating" || !promptReady;
  const imageActive = ["image_generating", "agent_generating"].includes(figure.status)
    || (promptReady && !imageReady && figure.status !== "prompt_generating");
  const paperActive = ["agent_generating", "agent_editing"].includes(figure.status)
    || (imageReady && !paperReady && figure.status !== "image_generating");
  const stages = [
    {
      id: "prompt",
      ready: promptReady,
      active: promptActive,
      status: figure.status === "prompt_generating" ? studioT("生成中", "Generating") : (promptReady ? studioT("已就绪", "Ready") : studioT("待生成", "To be generated")),
    },
    {
      id: "image",
      ready: imageReady,
      active: imageActive,
      status: ["image_generating", "agent_generating"].includes(figure.status)
        ? studioT("绘制中", "Drawing in progress") : (imageReady ? studioT("已完成", "Completed") : studioT("等待 Prompt", "Waiting for Prompt")),
    },
    {
      id: "paper",
      ready: paperReady,
      active: paperActive,
      status: ["agent_generating", "agent_editing"].includes(figure.status)
        ? studioT("自动重建中", "Auto-rebuilding.")
        : (paperReady ? studioT("已完成", "Completed") : studioT("随后自动重建", "Then automatically rebuild.")),
    },
  ];
  stages.forEach((stage) => {
    const node = $(`mechanism-flow-${stage.id}`);
    node.classList.toggle("is-complete", stage.ready);
    node.classList.toggle("is-active", stage.active);
    node.setAttribute("aria-current", stage.active ? "step" : "false");
    $(`mechanism-flow-${stage.id}-status`).textContent = stage.status;
  });
}

function updateFigureButtonStates() {
  const figure = selectedFigure();
  if (!figure) return;
  const running = figureIsRunning(figure) || figureRequestBusy;
  const table = figure.kind === "table";
  const generationReady = figure.generation_ready !== false;
  const insertionReady = figure.insertion_ready === undefined
    ? figure.ready
    : figure.insertion_ready;
  const captionDirty = $("figure-caption").dataset.dirty === "true";
  const captionNeedsBackfill = Boolean(figure.caption_needs_backfill);
  const submittedPrompt = $("draw-prompt").value.trim();
  const promptInstruction = $("prompt-instruction").value.trim();
  $("figure-prompt").disabled = state.demo_mode
    || !figure.ready || !generationReady || running || Boolean(submittedPrompt && !promptInstruction);
  $("figure-draw").disabled = !figure.ready || !generationReady || running || !submittedPrompt;
  $("figure-draw").textContent = figure.paper_preview_url
    ? studioT("确认新 Prompt → 重绘", "Confirm new Prompt → Redraw")
    : studioT("确认 Prompt → Codex 绘图", "Confirm prompt → draw");
  $("figure-cancel").hidden = figure.status !== "image_generating";
  $("figure-cancel").disabled = figure.status !== "image_generating" || figureRequestBusy;
  const mechanismBuildFailed = Boolean(
    figure.kind === "mechanism"
    && figure.status === "failed"
    && figure.draw_prompt
    && !figure.paper_preview_url
  );
  $("figure-build").hidden = !mechanismBuildFailed;
  $("figure-build").disabled = !figure.ready || !generationReady || running || !figure.preview_url;
  $("figure-build").textContent = studioT("重试可编辑 PPT/PDF 重建", "Retry editable PPT/PDF reconstruction.");
  $("figure-approve").disabled = (
    table
    || !insertionReady
    || !(figure.downloads || {}).pdf
    || !(figure.downloads || {}).pptx
    || (figure.status === "approved" && !captionDirty && !captionNeedsBackfill)
  );
  const panelsReady = (figure.panels || []).length > 0 && (figure.panels || []).every((panel) => panel.status === "built");
  const loadedCandidate = $("figure-preview-pdf").dataset.loaded;
  const expectedCandidate = figure.preview_url
    ? `${figure.preview_url}#toolbar=0&navpanes=0&view=FitH`
    : "";
  $("data-compose").disabled = table || !figure.ready || running || !panelsReady;
  $("single-data-generate").disabled = table || !figure.ready || running;
  $("data-compose").textContent = figure.composition_ready
    ? studioT("重新解析 Prompt 并生成合成图", "Reparse the Prompt and generate a composite image.")
    : studioT("合成图", "Composite figure");
  $("data-approve").disabled = (
    table
    || !insertionReady
    || !figure.composition_ready
    || !(figure.downloads || {}).pdf
    || loadedCandidate !== expectedCandidate
  );
  $("data-approve-after-placement").hidden = !(
    figure.kind === "data"
    && figure.composition_ready
    && loadedCandidate === expectedCandidate
  );
  const hasPlacement = (figure.placement_options || []).some((option) => option.accepted);
  $("figure-placement").disabled = running || !hasPlacement;
  $("figure-layout-mode").disabled = running || !hasPlacement;
  $("figure-approve").textContent = figure.status === "approved"
    ? (captionDirty
      ? studioT("更新 Caption → PDF", "Update Caption → PDF")
      : captionNeedsBackfill
        ? studioT("补生成 Caption → PDF", "Generate additional caption. → PDF")
        : studioT("已插入正文", "Body text has been inserted."))
    : studioT("确认并插入正文", "Confirm and insert the body text");
  $("data-approve").textContent = figure.status === "approved"
    ? (captionDirty
      ? studioT("更新 Caption → PDF", "Update Caption → PDF")
      : captionNeedsBackfill
        ? studioT("补生成 Caption → PDF", "Generate additional caption. → PDF")
        : studioT("重新插入", "Reinsert"))
    : studioT("确认并插入正文", "Confirm and insert the body text");
  const visibleTableLatex = $("table-latex").value.trim();
  const tableLatexDirty = $("table-latex").dataset.dirty === "true";
  $("table-generate").disabled = !table || !figure.ready || running;
  $("table-agent-edit").disabled = !table || !figure.ready || running || !visibleTableLatex;
  $("table-save").disabled = !table || running || !visibleTableLatex || !tableLatexDirty;
  $("table-save").textContent = figure.status === "approved" && tableLatexDirty
    ? studioT("保存修改（需重新确认）", "Save changes (requires reconfirmation).")
    : studioT("保存修改", "Save changes");
  $("table-approve").disabled = (
    !table
    || !figure.ready
    || running
    || !visibleTableLatex
    || (figure.status === "approved" && !tableLatexDirty)
  );
  $("table-approve").textContent = figure.status === "approved"
    ? (tableLatexDirty ? studioT("更新表格 → PDF", "Update table → PDF") : studioT("已插入正文", "Body text has been inserted."))
    : studioT("确认并插入正文", "Confirm and insert the body text");
  $("figure-caption").disabled = table || running;
  $("figure-caption-prompt").disabled = table || running;
  $("figure-caption-generate").disabled = table || running;
  $("figure-caption-save").disabled = table || running || !captionDirty;
  $("figure-caption-save").textContent = figure.status === "approved"
    ? studioT("保存 Caption 并更新 PDF", "Save caption and update PDF.")
    : studioT("保存 Caption", "Save caption");
  $("draw-prompt").disabled = running;
  $("prompt-instruction").disabled = running;
  $("single-data-prompt").disabled = running;
  $("data-layout-prompt").disabled = running;
  $("table-prompt").disabled = running;
  $("table-agent-prompt").disabled = running;
  $("table-latex").disabled = running;
  document.querySelectorAll(".data-panel textarea").forEach((control) => {
    control.disabled = running;
  });
  document.querySelectorAll(".data-panel button").forEach((control) => {
    control.disabled = running || !figure.ready;
  });
  // Preview load callbacks also refresh these controls after render() returns.
  applyReadOnlyDemoRestrictions();
  applyDraftJobRestrictions();
}

function renderSingleDataFigure(figure) {
  const panel = (figure.panels || [])[0];
  if (!panel) return;
  $("data-panels").replaceChildren();
  $("data-panels").dataset.figureId = figure.id;
  const input = $("single-data-prompt");
  renderFigureEditorInput(input, figure.id, `panel:${panel.id}`, panel.agent_prompt || "");
  const generate = $("single-data-generate");
  const generatorName = state.online_project ? "Python" : studioT("本地 Agent", "Local Agent");
  generate.textContent = panel.preview_url
    ? studioT(`${generatorName} 重新生成这张图`, `${generatorName} Regenerate this figure`)
    : studioT(`${generatorName} 生成这张图`, `${generatorName} Generate this figure.`);
  generate.onclick = () => startFigureJob(
    "/api/figure/panel/generate",
    {
      figure_id: figure.id,
      panel_id: panel.id,
      agent_prompt: input.value,
      layout_prompt: "",
      layout_width: $("figure-layout-mode").value === "two-column"
        ? "two-column"
        : "single-column",
    },
    studioT(`正在生成 ${figure.id} 最终单图…`, `Generating ${figure.id} Final single figure…`),
  );
}

function renderDataPanels(figure) {
  const root = $("data-panels");
  if (root.dataset.figureId !== figure.id) {
    root.replaceChildren();
    root.dataset.figureId = figure.id;
  }
  const expectedPanels = new Set((figure.panels || []).map((panel) => panel.id));
  root.querySelectorAll(".data-panel").forEach((card) => {
    if (!expectedPanels.has(card.dataset.panelId)) card.remove();
  });
  (figure.panels || []).forEach((panel) => {
    let card = [...root.querySelectorAll(".data-panel")].find(
      (item) => item.dataset.panelId === panel.id,
    );
    if (!card) {
      card = document.createElement("section");
      card.className = "data-panel";
      card.dataset.panelId = panel.id;
      card.innerHTML = `
        <div class="data-panel-head"><strong></strong><span class="status"></span></div>
        <div class="data-panel-preview"></div>
        <div class="figure-progress data-panel-progress" hidden>
          <progress class="figure-progress-track" max="100" value="0"></progress><strong></strong>
        </div>
        <label class="data-panel-prompt-label">${studioT("这张子图的修改 Prompt", "Modification prompt for this subfigure")}</label>
        <textarea class="data-panel-prompt" rows="3" placeholder="${studioT("例如：缩短标题，把图例移到右上角；只调整这张图，不改数据。", "For example shorten the title and move the legend to the upper right corner; only adjust this figure and do not change the data.")}"></textarea>
        <div class="data-panel-actions"><button class="primary data-panel-generate"></button></div>
        <pre class="message data-panel-message" hidden></pre>
      `;
      card.querySelector(".data-panel-prompt").addEventListener("input", (event) => {
        event.currentTarget.dataset.dirty = "true";
        const currentFigure = selectedFigure();
        if (currentFigure) {
          const currentPanel = (currentFigure.panels || []).find(
            (item) => item.id === card.dataset.panelId,
          );
          rememberFigureEditorDraft(
            currentFigure.id,
            `panel:${card.dataset.panelId}`,
            event.currentTarget.value,
            (currentPanel && currentPanel.agent_prompt) || "",
          );
        }
      });
      root.appendChild(card);
    }

    const singlePanel = (figure.panels || []).length === 1;
    const title = card.querySelector(".data-panel-head strong");
    title.textContent = singlePanel
      ? `${figure.id} · ${figure.title}`
      : `${figure.id}(${panel.id}) · ${panel.title}`;
    card.querySelector(".data-panel-prompt-label").textContent = singlePanel
      ? studioT("这张图的修改 Prompt", "Modification prompt for this figure.")
      : studioT("这张子图的修改 Prompt", "Modification prompt for this subfigure.");
    const status = card.querySelector(".data-panel-head .status");
    status.className = `status ${panel.status === "built" ? "ok" : ""}`;
    status.textContent = panel.status;

    const preview = card.querySelector(".data-panel-preview");
    if (panel.preview_url) {
      if (panel.preview_type === "pdf") {
        const target = `${panel.preview_url}#toolbar=0&navpanes=0&view=FitH`;
        let frame = preview.querySelector(".data-panel-pdf");
        if (!frame || frame.dataset.source !== target) {
          frame = document.createElement("iframe");
          frame.className = "data-panel-pdf";
          frame.src = target;
          frame.dataset.source = target;
          frame.title = singlePanel
            ? `${figure.id} ${studioT("矢量 PDF 候选", "vector PDF candidate")}`
            : `${figure.id}(${panel.id}) ${studioT("矢量 PDF 候选", "vector PDF candidate")}`;
          preview.replaceChildren(frame);
        }
      } else {
        let panelImage = preview.querySelector("img");
        if (!panelImage || panelImage.dataset.source !== panel.preview_url) {
          panelImage = document.createElement("img");
          panelImage.src = panel.preview_url;
          panelImage.dataset.source = panel.preview_url;
          panelImage.alt = `${figure.id}(${panel.id}) ${studioT("预览", "preview")}`;
          preview.replaceChildren(panelImage);
        }
      }
    } else {
      if (!preview.querySelector(".data-panel-empty")) {
        const panelEmpty = document.createElement("div");
        panelEmpty.className = "data-panel-empty";
        panelEmpty.textContent = singlePanel ? studioT("尚未生成这张图", "This figure has not yet been generated.") : studioT("尚未生成这张独立子图", "This independent subfigure has not yet been generated");
        preview.replaceChildren(panelEmpty);
      }
    }

    const progress = card.querySelector(".data-panel-progress");
    progress.hidden = panel.status !== "agent_generating";
    progress.querySelector(".figure-progress-track").value = Math.max(0, Math.min(100, panel.progress || 0));
    progress.querySelector("strong").textContent = panel.progress_message
      || (singlePanel ? studioT("本地 Agent 正在处理这张图…", "Local Agent is processing this figure…") : studioT("本地 Agent 正在处理这张子图…", "Local Agent is processing this sub-figure."));

    const input = card.querySelector(".data-panel-prompt");
    renderFigureEditorInput(input, figure.id, `panel:${panel.id}`, panel.agent_prompt || "");
    const generate = card.querySelector(".data-panel-generate");
    generate.textContent = panel.preview_url ? studioT("本地 Agent 重新生成这张", "Local Agent regenerates this.") : studioT("本地 Agent 生成这张", "Local agent generated this.");
    generate.onclick = () => startFigureJob(
      "/api/figure/panel/generate",
      {
        figure_id: figure.id,
        panel_id: panel.id,
        agent_prompt: input.value,
        layout_prompt: $("data-layout-prompt").value,
        layout_width: $("figure-layout-mode").value === "two-column"
          ? "two-column"
          : "single-column",
      },
      singlePanel
        ? studioT(`正在生成 ${figure.id} 最终单图…`, `Generating ${figure.id} Final single figure…`)
        : studioT(`正在单独生成 ${figure.id}(${panel.id})…`, `Generating separately ${figure.id}(${panel.id})…`),
    );
    const panelMessage = card.querySelector(".data-panel-message");
    panelMessage.hidden = !panel.last_message;
    panelMessage.textContent = panel.last_message || "";
  });
}

function scheduleAutomaticDataPanel(figure) {
  if (
    activeView !== "figures"
    || figure.kind !== "data"
    || !figure.ready
    || figure.generation_ready === false
    || figureIsRunning(figure)
  ) return;
  const nextPanel = (figure.panels || []).find(
    (panel) => panel.status === "pending" && !panel.preview_url,
  );
  if (!nextPanel) return;
  const attemptKey = `${figure.id}:${nextPanel.id}`;
  if (autoDataPanelAttempted.has(attemptKey)) return;
  autoDataPanelAttempted.add(attemptKey);
  setTimeout(() => {
    const current = selectedFigure();
    if (
      !current
      || current.id !== figure.id
      || current.generation_ready === false
      || figureIsRunning(current)
    ) return;
    const currentNext = (current.panels || []).find(
      (panel) => panel.status === "pending" && !panel.preview_url,
    );
    if (!currentNext || currentNext.id !== nextPanel.id) return;
    if (figureRequestBusy) {
      // Switching figures immediately after an approval can race with the
      // previous request's finally block. Do not consume this figure's only
      // automatic attempt while the shared request lock is still held.
      autoDataPanelAttempted.delete(attemptKey);
      setTimeout(() => scheduleAutomaticDataPanel(current), 100);
      return;
    }
    const singlePanel = (current.panels || []).length === 1;
    const card = [...$("data-panels").querySelectorAll(".data-panel")].find(
      (item) => item.dataset.panelId === currentNext.id,
    );
    const agentPrompt = singlePanel
      ? $("single-data-prompt").value
      : (card && card.querySelector(".data-panel-prompt").value) || "";
    startFigureJob(
      "/api/figure/panel/generate",
      {
        figure_id: current.id,
        panel_id: currentNext.id,
        agent_prompt: agentPrompt,
        layout_prompt: singlePanel ? "" : $("data-layout-prompt").value,
        layout_width: $("figure-layout-mode").value === "two-column"
          ? "two-column"
          : "single-column",
      },
      singlePanel
        ? studioT(`正在自动生成 ${current.id} 最终单图 candidate…`, `Auto-generating. ${current.id} Final single figure candidate…`)
        : studioT(`正在自动生成 ${current.id}(${currentNext.id})；完成后继续下一张…`, `Auto-generating. ${current.id}(${currentNext.id}); Continue to the next figure after completion…`),
    );
  }, 50);
}

function scheduleAutomaticTableGenerate(figure) {
  // Reported directly: a researcher clicked into an empty table and nothing
  // happened -- generating one required finding "table-generate", which
  // sits inside the collapsed Advanced <details> disclosure. Data
  // figures already auto-generate the moment their panel is viewable (see
  // scheduleAutomaticDataPanel above); tables never had the equivalent, so
  // this mirrors that same pattern instead of requiring a manual click.
  if (
    activeView !== "tables"
    || figure.kind !== "table"
    || !figure.ready
    || figure.status !== "pending"
    || figureIsRunning(figure)
  ) return;
  if (autoTableGenerateAttempted.has(figure.id)) return;
  autoTableGenerateAttempted.add(figure.id);
  setTimeout(() => {
    const current = selectedFigure();
    if (
      !current
      || current.id !== figure.id
      || current.status !== "pending"
      || figureIsRunning(current)
    ) return;
    if (figureRequestBusy) {
      // Reported directly: switching straight from one pending table to
      // another (T1's auto-generate still in flight, then clicking into
      // T2) made T2 stay "pending" forever. runFigureAction shares one
      // global busy lock across every figure/table action and silently
      // no-ops while it's held -- but this function had already marked
      // T2 "attempted" before learning that, so it could never retry.
      // Un-mark it so the next render (state polling already runs
      // continuously) schedules a fresh attempt once the lock clears.
      autoTableGenerateAttempted.delete(figure.id);
      return;
    }
    runFigureAction(
      "/api/table/generate",
      {
        table_id: current.id,
        generation_prompt: $("table-prompt").value,
      },
      studioT(`正在自动生成 ${current.id} 表格初稿…`, `Auto-generating. ${current.id} Table draft…`),
    );
  }, 50);
}

function renderLayoutPrompt(figure) {
  const input = $("data-layout-prompt");
  const singlePanel = (figure.panels || []).length === 1;
  renderFigureEditorInput(input, figure.id, "layout_prompt", figure.layout_prompt || "");
  const plan = figure.layout_plan || {};
  $("data-workflow-note").textContent = singlePanel
    ? studioT("这是一张独立单图：点击下方按钮后直接生成最终 PDF candidate，不添加子图角标。", "This is a standalone single figure: click the button below to directly generate the final PDF candidate without subfigure corner marks.")
    : studioT("请分别生成并检查每张 PDF candidate。全部满意后，再手动点击“合成图”生成 PPTX 与矢量 PDF candidate。", "Please generate and review each PDF candidate separately. When all are satisfactory, manually click Synthesize Figure to generate PPTX and vector PDF candidates.");
  $("data-layout-prompt-label").hidden = singlePanel;
  input.hidden = singlePanel;
  $("data-compose-actions").hidden = singlePanel;
  $("data-composition-editor").hidden = singlePanel;
  $("single-data-controls").hidden = !singlePanel;
  $("data-panels").hidden = singlePanel;
  $("data-layout-plan-wrap").hidden = singlePanel || !Object.keys(plan).length;
  $("data-layout-plan").textContent = Object.keys(plan).length
    ? JSON.stringify(plan, null, 2)
    : "";
}

function markFigurePdfLoaded(figureId, target) {
  const pdf = $("figure-preview-pdf");
  const current = selectedFigure();
  if (!current || current.id !== figureId || pdf.dataset.source !== target) return;
  pdf.dataset.loaded = target;
  if (current.kind === "data" && current.composition_ready) {
    $("data-approve-after-placement").hidden = false;
  }
  updateFigureButtonStates();
}

function verifyFigurePdfCandidate(figureId, previewUrl, target) {
  const pdf = $("figure-preview-pdf");
  if (pdf.dataset.verifying === target || pdf.dataset.loaded === target) return;
  pdf.dataset.verifying = target;
  fetch(previewUrl, {cache: "no-store"})
    .then(async (response) => {
      if (!response.ok) return;
      let prefix = new Uint8Array();
      if (response.body && response.body.getReader) {
        const reader = response.body.getReader();
        const chunk = await reader.read();
        prefix = chunk.value || prefix;
        await reader.cancel().catch(() => {});
      } else {
        prefix = new Uint8Array(await response.arrayBuffer());
      }
      const pdfHeader = String.fromCharCode(...prefix.slice(0, 5)) === "%PDF-";
      if (!pdfHeader) return;
      markFigurePdfLoaded(figureId, target);
    })
    .catch(() => {
      // The iframe may still emit load; leave insertion locked until either check succeeds.
    })
    .finally(() => {
      if (pdf.dataset.verifying === target) delete pdf.dataset.verifying;
    });
}

function renderFigures() {
  syncCaptionDraftProject();
  syncFigureEditorDraftProject();
  const figures = sectionFigures();
  if (!figures.some((figure) => figure.id === activeFigure) && figures.length) {
    activeFigure = figures[0].id;
    try {
      localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
    } catch (_error) {}
  }
  const cards = $("figure-cards");
  cards.innerHTML = "";
  const tableMode = activeView === "tables";
  $("section-kicker").textContent = tableMode ? "SECTION TABLES" : "SECTION FIGURES";
  $("section-title").textContent = studioT(`${state.sections[activeSection].title} · ${tableMode ? "表" : "图"}`, `${state.sections[activeSection].title} · ${tableMode ? "table" : "figure"}`);
  if (!figures.length) {
    cards.innerHTML = studioT(`<div class="data-note">当前自然段和 section 没有计划中的 ${tableMode ? "table" : "figure"}。</div>`, `<div class="data-note">The current paragraph and section do not have the planned structure. ${tableMode ? "table" : "figure"}.</div>`);
    $("figure-detail").hidden = true;
    return;
  }
  $("figure-detail").hidden = false;
  figures.forEach((figure) => {
    const button = document.createElement("button");
    button.className = `figure-card${figure.id === activeFigure ? " selected" : ""}${figure.ready ? "" : " blocked"}`;
    button.innerHTML = `
      <span class="figure-card-id">${figure.id}</span>
      <span><strong>${figure.title}</strong><small>${figure.placeholder_only ? studioT("线上不提供画图表功能", "Online service does not provide charting functionality.") : figure.kind === "table" ? studioT("结果表 · 可编辑 LaTeX", "Results table · Editable LaTeX.") : figure.kind === "source" ? studioT("来源图 · 参考论文证据", "Source figure · Reference paper evidence.") : figure.kind === "mechanism" ? studioT("机制图 · 先完成", "Mechanism diagram · finish first") : studioT("数据图 · results/ 驱动", "Data figure · results/ driver.")}</small></span>
      <span class="figure-card-state ${figure.placeholder_only ? "placeholder" : figure.status}">${figure.placeholder_only ? "placeholder" : figure.ready ? figure.status : "locked"}</span>
    `;
    button.onclick = () => {
      activeFigure = figure.id;
      try {
        localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
      } catch (_error) {}
      renderFigures();
    };
    cards.appendChild(button);
  });

  const figure = selectedFigure();
  if (!figure) return;
  const isTable = figure.kind === "table";
  const sourceFigure = figure.kind === "source";
  const placeholderOnly = Boolean(figure.placeholder_only);
  $("figure-phase").textContent = placeholderOnly
    ? "PHASE PLACEHOLDER"
    : `PHASE ${figure.phase || "SOURCE"} · ${figure.kind === "table" ? "EDITABLE TABLE" : sourceFigure ? "VERIFIED SOURCE FIGURE" : figure.kind === "mechanism" ? "EDITABLE SCHEMATIC" : "DATA FIGURE"}`;
  $("figure-title").textContent = `${figure.id} · ${figure.title}`;
  $("figure-description").textContent = `${figure.description} · ${figure.width} · ${figure.label}`;
  document.querySelector("#figure-detail .figure-detail-head").hidden = placeholderOnly;
  $("figure-phase").hidden = placeholderOnly;
  $("figure-title").hidden = placeholderOnly;
  $("figure-description").hidden = placeholderOnly;
  const gate = $("figure-gate");
  const insertionBlocked = figure.insertion_ready === false;
  gate.textContent = !figure.ready
    ? figure.gate_reason
    : insertionBlocked
      ? figure.insertion_gate_reason
      : "";
  gate.hidden = placeholderOnly;
  gate.classList.toggle("show", !placeholderOnly && (!figure.ready || insertionBlocked));
  const onlinePlaceholder = $("online-figure-placeholder");
  onlinePlaceholder.hidden = !placeholderOnly;
  $("online-figure-placeholder-message").textContent = placeholderOnly
    ? figure.placeholder_message
    : "";
  const mechanismPrerequisite = $("mechanism-generation-prerequisite");
  const mechanismPrerequisiteBlocked = (
    figure.kind === "mechanism" && figure.generation_ready === false
  );
  mechanismPrerequisite.hidden = placeholderOnly || !mechanismPrerequisiteBlocked;
  $("mechanism-generation-prerequisite-text").textContent = mechanismPrerequisiteBlocked
    ? figure.generation_gate_reason
    : "";

  const progress = $("figure-progress");
  const running = figureIsRunning(figure);
  const singleData = figure.kind === "data" && (figure.panels || []).length === 1;
  progress.hidden = !running || (figure.kind === "data" && !singleData);
  $("figure-progress-bar").value = Math.max(0, Math.min(100, figure.progress || 0));
  const elapsed = running && Number.isFinite(figure.running_seconds)
    ? studioT(` · 已等待 ${figure.running_seconds} 秒`, ` · Waiting ${figure.running_seconds} seconds`)
    : "";
  $("figure-progress-message").textContent = `${figure.progress_message || ""}${elapsed}`;

  const mechanismPreviewSwitch = $("mechanism-preview-switch");
  const mechanismPreviewToggle = $("mechanism-preview-toggle");
  const mechanismPreviewNote = $("mechanism-preview-note");
  const mechanismBuildStatus = $("mechanism-build-status");
  const paperVersionInserted = Boolean(
    figure.status === "approved"
    && figure.paper_preview_url
  );
  const hasMechanismVersions = false;
  let mechanismPreviewMode = mechanismPreviewModes.get(figure.id) || "paper";
  if (!hasMechanismVersions || paperVersionInserted) {
    mechanismPreviewModes.delete(figure.id);
    mechanismPreviewMode = "paper";
  }
  mechanismPreviewSwitch.hidden = !hasMechanismVersions;
  const mechanismBuildPending = (
    figure.kind === "mechanism"
    && ["image_generating", "agent_generating"].includes(figure.status)
    && !figure.paper_preview_url
  );
  mechanismBuildStatus.hidden = !mechanismBuildPending;
  mechanismBuildStatus.textContent = mechanismBuildPending
    ? (["agent_generating", "agent_editing"].includes(figure.status)
      ? studioT("绘图已完成；可编辑 PPT/PDF 正在后台生成。", "Generating editable PPT and PDF in the background.")
      : figure.status === "failed"
        ? studioT(`可编辑 PPT/PDF 重建失败：${figure.last_message || figure.progress_message || "请点击重试。"}`, `Editable PPT/PDF reconstruction failed.${figure.last_message || figure.progress_message || "Please click Retry."}`)
        : studioT("可编辑 PPT/PDF 尚未完成；请重新运行 Codex 绘图。", "Editable PPT/PDF is not yet complete; please re-run the drawing."))
    : "";
  const textFreeDraftPreview = Boolean(figure.draft_preview_no_text);
  mechanismPreviewToggle.textContent = mechanismPreviewMode === "paper"
    ? (textFreeDraftPreview ? studioT("显示构图底图（无文字）", "Show layout draft (no text)") : studioT("显示构图草稿", "Show composition draft"))
    : studioT("显示可编辑 PPT/PDF 完整版", "Show editable PPT/PDF full version");
  mechanismPreviewNote.textContent = paperVersionInserted
    ? studioT("当前预览与正文 PDF 使用同一个图文件。", "The current preview and the main PDF use the same image file.")
    : textFreeDraftPreview
      ? studioT("草稿仅作构图参考；标签和图注文字在可编辑 PPT/PDF 版本中。", "The draft is a layout reference; labels and caption text reside in the editable PPT/PDF version.")
      : studioT("草稿仅供视觉审阅；插入和下载使用可编辑 PPT/PDF 版本。", "The draft is for visual review; insertion and download use the editable PPT/PDF version.");
  const effectivePreviewUrl = placeholderOnly
    ? null
    : (figure.paper_preview_url || figure.preview_url);
  const effectivePreviewType = figure.paper_preview_url ? "pdf" : figure.preview_type;

  const image = $("figure-preview-image");
  const pdf = $("figure-preview-pdf");
  const tablePreview = $("table-preview");
  image.hidden = true;
  pdf.hidden = true;
  tablePreview.hidden = true;
  if (isTable) {
    if (effectivePreviewUrl) {
      image.src = effectivePreviewUrl;
      image.alt = `${figure.id} ${studioT("LaTeX 编译表格预览", "LaTeX-compiled table preview")}`;
      image.hidden = false;
    }
  } else if (effectivePreviewUrl && effectivePreviewType === "image") {
    image.src = effectivePreviewUrl;
    image.hidden = false;
  } else if (effectivePreviewUrl) {
    const target = `${effectivePreviewUrl}#toolbar=0&navpanes=0&view=FitH`;
    if (pdf.dataset.source !== target) {
      pdf.dataset.loaded = "";
      $("data-approve-after-placement").hidden = true;
      pdf.onload = () => {
        verifyFigurePdfCandidate(figure.id, effectivePreviewUrl, target);
      };
      pdf.dataset.source = target;
      pdf.src = target;
      verifyFigurePdfCandidate(figure.id, effectivePreviewUrl, target);
    }
    pdf.hidden = false;
  }

  const mechanism = figure.kind === "mechanism" && !placeholderOnly;
  const captionBox = $("figure-caption-box");
  captionBox.hidden = isTable || placeholderOnly;
  const captionInput = $("figure-caption");
  const changedCaptionFigure = captionInput.dataset.figureId !== figure.id;
  const savedCaption = figure.caption || "";
  const generatedAt = String(figure.caption_generated_at || "");
  const captionDraftRecord = captionDrafts.get(figure.id);
  const automaticCaptionChanged = Boolean(
    captionDraftRecord
    && figure.caption_source === "paragraph_accept"
    && String(captionDraftRecord.generatedAt || "") !== generatedAt
  );
  if (automaticCaptionChanged) {
    // A newly accepted citing paragraph owns the canonical caption. Discard an
    // older browser draft so it cannot hide the caption that was just generated.
    forgetCaptionDraft(figure.id);
  }
  const refreshedCaptionDraftRecord = captionDrafts.get(figure.id);
  const captionDraft = refreshedCaptionDraftRecord
    ? refreshedCaptionDraftRecord.value
    : undefined;
  if (captionDraft === savedCaption) {
    forgetCaptionDraft(figure.id);
  }
  if (changedCaptionFigure || automaticCaptionChanged) {
    captionInput.value = captionDraft !== undefined && captionDraft !== savedCaption
      ? captionDraft
      : savedCaption;
    captionInput.dataset.figureId = figure.id;
    captionInput.dataset.dirty = String(captionInput.value !== savedCaption);
  } else if (captionInput.dataset.dirty !== "true" && document.activeElement !== captionInput) {
    captionInput.value = savedCaption;
    captionInput.dataset.dirty = "false";
  }
  captionInput.dataset.captionGeneratedAt = generatedAt;
  const captionPrompt = $("figure-caption-prompt");
  renderFigureEditorInput(captionPrompt, figure.id, "caption_prompt", "");
  const captionDirty = captionInput.dataset.dirty === "true";
  const automaticCaptionStatus = figure.caption_last_error
    ? studioT(`自动 Caption 生成失败：${figure.caption_last_error}`, `Automatic caption generation failed:${figure.caption_last_error}`)
    : (figure.caption_source === "paragraph_accept"
      ? studioT(`Caption 已在接受 ${figure.caption_generated_from_paragraph || "引用段落"} 时自动生成`, `Caption Has been accepted ${figure.caption_generated_from_paragraph || "Citation paragraph"} Auto-generating.`)
      : "");
  $("figure-caption-status").textContent = captionDirty
    ? (figure.status === "approved"
      ? studioT("Caption 已修改，尚未更新到正文与 PDF", "Caption Modified, not yet updated in the main text and PDF.")
      : studioT("Caption 已修改，尚未保存", "Caption Modified, not yet saved"))
    : automaticCaptionStatus
      ? automaticCaptionStatus
    : (figure.status === "approved"
      ? studioT("Caption 已写入正文与 PDF", "Caption Written into main text and PDF")
      : studioT("当前正文将使用此 Caption", "The current main text will use this caption."));
  $("mechanism-controls").hidden = !mechanism;
  $("mechanism-approve-after-placement").hidden = !mechanism;
  $("data-controls").hidden = placeholderOnly || mechanism || isTable || sourceFigure;
  $("table-agent-controls").hidden = !isTable || Boolean(state.online_project);
  $("table-controls").hidden = !isTable || placeholderOnly;
  $("table-workflow-note").textContent = state.online_project
    ? studioT("上方图片由当前 LaTeX 真实编译；可生成结构化初稿并直接编辑 LaTeX。", "The image above is produced by the actual LaTeX compilation; it can generate a structured draft and allow direct LaTeX editing.")
    : studioT("上方图片由当前 LaTeX 真实编译。初稿与实验结果相关修改均由本地 Agent 完成。", "The top image is compiled by the current LaTeX; initial draft and experiment result related edits are performed by the local Agent.");
  $("table-generate").textContent = state.online_project ? studioT("生成表格初稿", "Generate initial table draft") : studioT("本地 Agent 生成初稿", "Local agent generated the first draft.");
  renderFigureEditorInput(
    $("table-prompt"),
    figure.id,
    "table_generation_prompt",
    figure.generation_prompt || "",
  );
  renderFigureEditorInput(
    $("table-agent-prompt"),
    figure.id,
    "table_agent_prompt",
    figure.agent_prompt || "",
  );
  if (!mechanism && !isTable && !sourceFigure) {
    renderLayoutPrompt(figure);
    if ((figure.panels || []).length === 1) {
      renderSingleDataFigure(figure);
    } else {
      renderDataPanels(figure);
    }
  }
  renderFigureEditorInput($("table-latex"), figure.id, "table_latex", figure.latex || "");
  renderFigureEditorInput($("draw-prompt"), figure.id, "draw_prompt", figure.draw_prompt || "");
  renderFigureEditorInput(
    $("prompt-instruction"),
    figure.id,
    "prompt_instruction",
    figure.prompt_instruction || "",
  );
  const placement = $("figure-placement");
  placement.innerHTML = "";
  (figure.placement_options || []).forEach((option) => {
    const item = document.createElement("option");
    item.value = option.id;
    item.textContent = studioT(`${option.id} 后${option.accepted ? "" : "（正文未完成）"}`, `${option.id} after${option.accepted ? "" : "(Main text not completed)"}`);
    item.disabled = !option.accepted;
    placement.appendChild(item);
  });
  if (figure.placement_after) placement.value = figure.placement_after;
  $("figure-placement-row").hidden = placeholderOnly;
  $("figure-layout-control").hidden = placeholderOnly;
  $("figure-layout-mode").value = figure.layout_mode || "single-column";
  $("figure-prompt").textContent = figure.draw_prompt
    ? studioT("按右侧指令更新 Prompt", "Update Prompt per the right side instructions.")
    : studioT("生成画图 Prompt", "Generate drawing prompt");
  updateMechanismFlow(figure);
  updateFigureButtonStates();

  const downloads = $("figure-downloads");
  downloads.innerHTML = "";
  Object.entries(figure.downloads || {}).forEach(([kind, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = studioT(`下载 ${kind.toUpperCase()}`, `download ${kind.toUpperCase()}`);
    link.download = "";
    downloads.appendChild(link);
  });
  downloads.hidden = placeholderOnly;
  const figureMessage = figure.last_message || "";
  $("figure-message").textContent = placeholderOnly ? "" : (
    figure.status === "approved" && state.compile?.status === "ok"
      && figureMessage === studioT("机制图已自动生成并插入，等待编译 PDF。", "The mechanism diagram has been automatically generated, inserted, and is awaiting PDF compilation.")
      ? studioT("机制图已插入，论文 PDF 已成功编译。", "The mechanism diagram has been inserted and the paper PDF compiled successfully.")
      : figureMessage
  );
  ensureFigurePolling();
  if (
    mechanism
    && figure.ready
    && figure.generation_ready !== false
    && figure.status === "pending"
    && !figure.draw_prompt
    && !autoFigurePromptAttempted.has(figure.id)
  ) {
    autoFigurePromptAttempted.add(figure.id);
    setTimeout(() => {
      const current = selectedFigure();
      if (
        activeView === "figures"
        && current
        && current.id === figure.id
        && current.generation_ready !== false
        && current.status === "pending"
      ) {
        startFigureJob(
          "/api/figure/prompt",
          {
            figure_id: figure.id,
            current_prompt: "",
            prompt_instruction: "",
          },
          studioT("正在根据当前 section 正文自动生成画图 Prompt…", "Automatically generating drawing prompts from the current section text."),
        );
      }
    }, 50);
  }
  scheduleAutomaticDataPanel(figure);
  scheduleAutomaticTableGenerate(figure);
}

const DEMO_READ_ONLY_CONTROL_IDS = [
  "generate", "accept", "candidate", "comment", "reset-generated",
  "section-draft-start",
  "compile", "model", "model-apply", "runtime-key-open",
  "title-generate", "title-save", "paper-title", "title-gpt-prompt",
  "figure-prompt", "draw-prompt", "prompt-instruction", "figure-draw",
  "figure-cancel", "figure-build", "single-data-prompt", "single-data-generate",
  "data-layout-prompt", "data-compose", "data-approve", "figure-caption-prompt",
  "figure-caption-save",
  "figure-caption-generate", "figure-placement", "figure-layout-mode",
  "figure-approve", "table-agent-prompt", "table-agent-edit", "table-prompt",
  "table-generate", "table-latex", "table-save", "table-approve",
];

function applyReadOnlyDemoRestrictions() {
  // The gateway already refuses every non-GET/HEAD request against a demo
  // session (server-side, unconditionally) -- this is UX only, so a demo
  // visitor sees a clean read-only viewer instead of controls that look
  // clickable and then dead-end in a network error.
  if (!state || !state.demo_mode) return;
  document.querySelectorAll("input, textarea, select, [contenteditable='true']")
    .forEach((element) => {
      element.disabled = true;
      element.setAttribute("contenteditable", "false");
      element.setAttribute("aria-readonly", "true");
    });
  DEMO_READ_ONLY_CONTROL_IDS.forEach((id) => {
    const element = $(id);
    if (element) element.disabled = true;
  });
  document.querySelectorAll(".figure-actions button, .data-panel-actions button")
    .forEach((element) => { element.disabled = true; });
}

function applyDraftJobRestrictions() {
  const running = [state?.full_draft?.job, state?.section_draft?.job]
    .some((job) => job?.status === "running");
  if (!running) return;
  // A workspace switch or a preview load must not unlock mutations while a
  // background writer owns the manuscript. Navigation and export remain usable.
  DEMO_READ_ONLY_CONTROL_IDS
    .forEach((id) => {
      const element = $(id);
      if (element) element.disabled = true;
    });
  document.querySelectorAll(".figure-actions button, .data-panel-actions button")
    .forEach((element) => { element.disabled = true; });
}

function render() {
  syncProseDraftProject();
  syncTitleDraftProject();
  syncCommentDraftProject();
  $("load-error").hidden = true;
  const project = state.project || {};
  const apiKeySetup = state.api_key_setup || {};
  const apiKeyReady = Boolean(state.api_key_configured);
  // Every online session (real or demo) shares one server-held DeepSeek
  // key; there is nothing for that researcher to pick, rotate, or type a
  // model name for, so both controls stay hidden there. A local desktop
  // install keeps them -- a solo researcher's own machine, their own key,
  // switching providers/models deliberately is unaffected.
  $("model-runtime-config").hidden = Boolean(state.online_project);
  $("runtime-key-open").hidden = Boolean(state.online_project);
  $("artifact-workflow-summary").textContent = state.online_project
    ? studioT("线上仅保留正文、可编辑表格与 Python 数据图；其他图以带 Caption 和 label 的 placeholder 写入论文。", "Online keep only the main text, editable tables, and Python data plots; other figures are inserted into the paper as placeholders with captions and labels.")
    : studioT("机制图单独设计；数据图和表格都从 results/ 生成，确认后插入对应自然段。", "Mechanism diagrams designed separately; data plots and tables are generated from results/ and inserted into the corresponding paragraph after confirmation.");
  const modelInput = $("model");
  const modelOptions = state.llm_model_options || [];
  $("model-suggestions").replaceChildren(...modelOptions.map((option) => {
    const element = document.createElement("option");
    element.value = option.id;
    element.label = option.label;
    return element;
  }));
  renderTitleDraftInput(modelInput, "model", state.model || "gpt-5-nano");
  updateModelApplyButton();
  $("api-key-setup").hidden = apiKeyReady;
  $("api-key-setup-command").textContent = apiKeySetup.setup_command || studioT('export OPENAI_API_KEY="粘贴你的 API key"', 'export OPENAI_API_KEY="Paste your API key."');
  $("api-key-setup-description").textContent = studioT(`${apiKeySetup.provider_label || "当前"} API 尚未配置。请在启动 Paper Studio 的本机终端设置；密钥不会进入网页。`, `${apiKeySetup.provider_label || "current"} API is not configured. Set it in the local terminal that launches Paper Studio; keys are never exposed to the web page. Mechanism figures are drawn locally as editable native shapes by Codex and do not require an image API.`);
  $("api-key-restart-command").textContent = apiKeySetup.restart_command || "python3 -m research_avatar.paper_studio.server";
  document.querySelector(".workspace").classList.toggle("api-key-missing", !apiKeyReady);
  $("studio-title").textContent = project.studio_title || "Paper Studio";
  const referencePaper = project.reference_paper || {};
  const referenceEl = $("project-reference-paper");
  if (referencePaper.title) {
    const meta = referencePaper.venue || "";
    referenceEl.replaceChildren();
    referenceEl.append(studioT("参考论文：", "Reference paper: "));
    if (referencePaper.url) {
      const link = document.createElement("a");
      link.href = referencePaper.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = referencePaper.title;
      referenceEl.append(link);
    } else {
      referenceEl.append(referencePaper.title);
    }
    if (meta) referenceEl.append(studioT(`（${meta}）`, ` (${meta})`));
    referenceEl.hidden = false;
  } else {
    referenceEl.hidden = true;
  }
  const projectExport = $("project-export");
  projectExport.hidden = !project.export_url;
  if (project.export_url) projectExport.href = studioPath(project.export_url);
  document.title = project.name ? `${project.name} · Paper Studio` : "Paper Studio";
  renderSections();
  const emptyMode = project.loaded === false;
  $("empty-project").hidden = !emptyMode;
  if (emptyMode) {
    $("writing-workspace").hidden = true;
    $("figures-workspace").hidden = true;
    $("section-kicker").textContent = "EMPTY STUDIO";
    $("section-title").textContent = studioT("尚未载入论文", "Paper not yet loaded.");
    ["writing-view", "figures-view", "tables-view", "compile", "reset-generated", "model", "model-apply", "runtime-key-open"].forEach((id) => {
      $(id).disabled = true;
    });
    return;
  }
  ["writing-view", "figures-view", "tables-view", "compile", "reset-generated", "model", "runtime-key-open"].forEach((id) => {
    $(id).disabled = false;
  });
  updateModelApplyButton();
  const artifactMode = ["figures", "tables"].includes(activeView);
  $("writing-workspace").hidden = artifactMode;
  $("figures-workspace").hidden = !artifactMode;
  $("writing-view").classList.toggle("active", !artifactMode);
  $("figures-view").classList.toggle("active", activeView === "figures");
  $("tables-view").classList.toggle("active", activeView === "tables");
  if (artifactMode) {
    $("section-kicker").textContent = activeView === "tables" ? "TABLE WORKFLOW" : "FIGURE WORKFLOW";
    $("section-title").textContent = activeView === "tables" ? "Tables" : "Figures";
    renderFigures();
    applyReadOnlyDemoRestrictions();
    applyDraftJobRestrictions();
    return;
  }
  $("section-kicker").textContent = "SECTION";
  const section = state.sections[activeSection];
  const planningOnly = section.writing_mode === "plan_only";
  $("section-title").textContent = section.title;
  $("title-editor").hidden = activeSection !== "abstract";
  if (activeSection === "abstract") renderTitleEditor();
  renderParagraphNavigation(section);
  renderReferenceContext(section);
  renderStructureBlueprint(section);
  const paragraph = section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  $("paragraph-id").textContent = paragraph ? paragraph.id : studioT("完成", "complete");
  $("paragraph-progress").textContent = paragraph
    ? `${paragraph.position} / ${paragraph.total}`
    : `${section.paragraph_count} / ${section.paragraph_count}`;
  $("candidate-label").textContent = paragraph
    ? candidate
      ? studioT("当前候选段落", "Current candidate paragraph.")
      : paragraph.accepted_text
        ? studioT("已接受版本（可继续修改）", "Accepted version (may still be modified).")
        : studioT("当前候选段落", "Current candidate paragraph.")
    : studioT("已接受并写入 LaTeX 的 section 内容", "Section content has been accepted and written in LaTeX.");
  const proseEditor = $("candidate");
  const editorKey = `${activeSection}:${paragraph ? paragraph.id : "complete"}`;
  const serverText = candidate
    ? candidate.text
    : paragraph
      ? paragraph.accepted_text || ""
      : section.accepted_text || "";
  let proseDraft = proseDrafts.get(editorKey);
  if (proseDraft && proseDraft.value === serverText) {
    forgetProseDraft(editorKey);
    proseDraft = undefined;
  }
  if (
    proseBaselineKey !== editorKey
    || (proseEditor.dataset.dirty !== "true" && document.activeElement !== proseEditor)
  ) {
    proseEditor.value = proseDraft ? proseDraft.value : serverText;
    proseEditor.dataset.dirty = String(Boolean(proseDraft));
    proseBaselineKey = editorKey;
    proseBaselineText = proseDraft ? proseDraft.baseline : serverText;
  }
  $("candidate").placeholder = planningOnly
    ? studioT("未上传实验结果：本 section 只保留段落主旨和待执行实验，不生成正文。", "No experimental results uploaded: this section only keeps paragraph aims and planned experiments, and does not generate body text.")
    : paragraph
    ? paragraph.accepted_text
      ? studioT("这是当前写入 LaTeX 的版本；填写 comment 后可继续修改。", "This is the current LaTeX version; after filling the comment you can continue to modify.")
      : studioT("等待生成当前段落…", "Waiting to generate the current paragraph…")
    : studioT("这个 section 已完成。", "This section is completed.");
  $("comment").value = commentDrafts.get(editorKey) || "";
  updateAcceptButton();
  $("candidate").disabled = planningOnly;
  $("comment").disabled = planningOnly;
  $("generate").disabled = !paragraph || planningOnly;
  $("generate").textContent = candidate || paragraph?.accepted_text
    ? studioT("修改段落", "Revise paragraph")
    : studioT("生成段落", "Generate paragraph");
  const gate = $("gate");
  gate.textContent = planningOnly
    ? studioT("未上传实验结果：从 Experiments 开始仅展示每段主旨、写作任务和待执行实验，不调用 LLM 生成正文。", "Experiment results not uploaded: starting from Experiments only display the main idea of each section, writing task, and pending experiments, without invoking LLM to generate the main text.")
    : state.outline_confirmed
    ? ""
    : studioT("Outline 尚未确认。可以浏览界面，但在确认并建立 LaTeX scaffold 前不能 Accept → LaTeX。", "Outline Not confirmed yet. You may browse the interface, but you cannot Accept until you confirm and establish the LaTeX scaffold. → LaTeX.");
  gate.classList.toggle("show", planningOnly || !state.outline_confirmed);
  renderFullDraft();
  renderPdf();
  const fullDraftRunning = Boolean(
    state.full_draft && state.full_draft.job && state.full_draft.job.status === "running"
  );
  const sectionDraftJob = state.section_draft && state.section_draft.job;
  const sectionDraftRunning = Boolean(
    sectionDraftJob && sectionDraftJob.status === "running"
  );
  const sectionDraftArtifactsPending = Boolean(
    sectionDraftJob && sectionDraftJob.status === "artifacts_pending"
  );
  if (sectionDraftRunning && !fullDraftPollTimer) {
    fullDraftPollTimer = setTimeout(pollFullDraft, 900);
  }
  const sectionPending = (section.paragraph_navigation || []).filter(
    (item) => item.status !== "accepted"
  ).length;
  const sectionDraftStart = $("section-draft-start");
  sectionDraftStart.disabled = Boolean(
    planningOnly
    || fullDraftRunning
    || sectionDraftRunning
    || sectionDraftArtifactsPending
    || fullDraftRequestBusy
    || Boolean(queuedSectionDraftStart)
    || !state.outline_confirmed
    || !state.api_key_configured
    || sectionPending === 0
  );
  const activeSectionArtifactJob = Boolean(
    sectionDraftArtifactsPending
    && sectionDraftJob.section === activeSection
  );
  const activeSectionRunningJob = Boolean(
    sectionDraftRunning && sectionDraftJob.section === activeSection
  );
  const sectionProgressVisible = Boolean(
    sectionDraftJob
    && sectionDraftJob.section === activeSection
    && ["running", "artifacts_pending"].includes(sectionDraftJob.status)
  );
  const sectionProgressRow = $("section-draft-progress-row");
  sectionProgressRow.hidden = !sectionProgressVisible;
  $("section-draft-progress").value = Number(sectionDraftJob?.progress || 0);
  $("section-draft-progress-text").textContent = sectionProgressVisible
    ? studioT(`已完成 ${Number(sectionDraftJob.completed || 0)} / ${Number(sectionDraftJob.total || sectionPending)} 段 · ${sectionDraftJob.progress_message || "正在生成当前 Section…"}`, `Completed ${Number(sectionDraftJob.completed || 0)} / ${Number(sectionDraftJob.total || sectionPending)} Section · ${sectionDraftJob.progress_message || "Generating current Section…"}`)
    : "";
  sectionDraftStart.textContent = activeSectionRunningJob
    ? studioT(`${sectionDraftJob.progress_message || "正在生成当前 Section…"}`, `${sectionDraftJob.progress_message || "Generating current Section…"}`)
    : activeSectionArtifactJob
    ? studioT(`正在完成本 Section 图表（${(sectionDraftJob.pending_artifacts || []).join("、")}）`, `Completing this Section chart (${(sectionDraftJob.pending_artifacts || []).join(", ")})`)
    : queuedSectionDraftStart === activeSection
    ? studioT("当前段落完成后自动生成本 Section…", "After the current paragraph completes, this Section will be generated automatically.")
    : sectionPending
      ? studioT(`一键生成当前 Section（${sectionPending} 段待完成）`, `Generate current section (${sectionPending} paragraphs remaining)`)
      : studioT("当前 Section 已完成", "The current section is complete");
  applyReadOnlyDemoRestrictions();
  applyDraftJobRestrictions();
}

function renderFullDraft() {
  if (state.demo_mode) return;
  const job = (state.full_draft || {}).job || null;
  const running = Boolean(job && job.status === "running");

  ["candidate", "comment", "generate", "section-draft-start", "accept", "paper-title", "title-gpt-prompt", "title-generate", "title-save", "model", "reset-generated"].forEach((id) => {
    const element = $(id);
    if (element && running) element.disabled = true;
  });
  document.querySelectorAll("#paragraph-nav button").forEach((button) => {
    button.disabled = running;
  });

  if (fullDraftPollTimer) {
    clearTimeout(fullDraftPollTimer);
    fullDraftPollTimer = null;
  }
  if (running) {
    fullDraftPollTimer = setTimeout(pollFullDraft, 900);
  }
}

async function pollFullDraft() {
  fullDraftPollTimer = null;
  try {
    state = normalizeStateUrls(await request("/api/state"));
    render();
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function refresh() {
  state = normalizeStateUrls(await request("/api/state"));
  if (state.project && state.project.loaded === false) {
    render();
    return;
  }
  if (!state.sections[activeSection]) {
    activeSection = state.sections.abstract ? "abstract" : Object.keys(state.sections)[0];
  }
  render();
}

async function generateCurrent(automatic = false) {
  if (proseRequestBusy) return;
  proseRequestBusy = true;
  const requestedSection = activeSection;
  const requestedParagraph = state.sections[requestedSection].current_paragraph;
  if (!requestedParagraph) {
    proseRequestBusy = false;
    return;
  }
  try {
    setBusy(true, automatic
      ? studioT("正在结合已批准的段落结构、working abstract 和实验结果生成当前段落…", "Currently combining approved paragraph structure working abstract and experimental results to generate the current paragraph.")
      : studioT("正在根据 comment 修改当前段落…", "Modifying the current paragraph based on the comment."));
    const payload = await request("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        section: requestedSection,
        paragraph_id: requestedParagraph.id,
        model: $("model").value.trim(),
        current_text: $("candidate").value,
        comment: $("comment").value,
      }),
    });
    state = payload.state;
    if (activeSection === requestedSection) {
      if (automatic && $("candidate").dataset.dirty === "true") {
        renderSections();
        updateAcceptButton();
        showMessage(studioT("后台 candidate 已生成；已保留你正在编辑的正文，Accept 时将以编辑框内容为准。", "Backend candidate has been generated; the text you are editing remains, and Accept will use the content from the editing box."));
        return;
      }
      forgetProseDraft(`${requestedSection}:${requestedParagraph.id}`);
      forgetCommentDraft(`${requestedSection}:${requestedParagraph.id}`);
      $("candidate").dataset.dirty = "false";
      render();
      showMessage(studioT("当前段落已生成。你只需要写 comment 修改，或 Accept → LaTeX。", "Current paragraph has been generated; you may write comment edits or Accept. → LaTeX."));
    } else {
      renderSections();
      showMessage(studioT(`${state.sections[requestedSection].title} 的当前段落已生成并保存。`, `${state.sections[requestedSection].title} The current paragraph has been generated and saved.`));
    }
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    proseRequestBusy = false;
    setBusy(false);
    if (queuedSectionDraftStart) {
      const section = queuedSectionDraftStart;
      queuedSectionDraftStart = "";
      void startSectionDraftFromBrowser(section);
    }
  }
}

$("generate").onclick = () => generateCurrent(false);

$("candidate").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  const paragraph = state.sections[activeSection].current_paragraph;
  if (paragraph) {
    rememberProseDraft(
      `${activeSection}:${paragraph.id}`,
      event.currentTarget.value,
      proseBaselineText,
    );
  }
  if (paragraph && paragraph.accepted_text && !paragraph.candidate) {
    $("candidate-label").textContent = studioT("已接受版本的手动修改（尚未写入）", "Manual edits of accepted version (not yet written).");
  }
  updateAcceptButton();
});

$("comment").addEventListener("input", (event) => {
  const paragraph = state.sections[activeSection].current_paragraph;
  if (paragraph) rememberCommentDraft(`${activeSection}:${paragraph.id}`, event.currentTarget.value);
});

async function applyWritingModel() {
  if (proseRequestBusy || fullDraftRequestBusy || titleBusy || modelApplyBusy) {
    return;
  }
  const requestedModel = $("model").value.trim();
  if (!requestedModel) {
    showMessage(studioT("请先输入写作模型名称。", "Please enter the writing model name first."), true);
    updateModelApplyButton();
    return;
  }
  if (requestedModel === state.model) return;
  if (!confirm(studioT(`切换到 ${requestedModel}？这会重置所有 LLM 对话链，但不会修改已写入的正文、图表或 PDF。`, `Switch to ${requestedModel}?This will reset all LLM chat history, but will not modify the already written body, figures, or PDF.`))) {
    return;
  }
  modelApplyBusy = true;
  try {
    setBusy(true, studioT(`正在切换写作模型为 ${requestedModel}…`, `Switching writing model to ${requestedModel}…`));
    const payload = await request("/api/llm-model", {
      method: "POST",
      body: JSON.stringify({model: requestedModel}),
    });
    state = payload.state;
    forgetTitleDraft("model");
    render();
    showMessage(studioT(`写作模型已切换为 ${state.model}；LLM 对话链已重置，已写入内容保持不变。`, `Writing model has been switched to ${state.model}; LLM Dialogue chain has been reset; written content remains unchanged.`));
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    modelApplyBusy = false;
    setBusy(false);
  }
}

$("model").addEventListener("input", (event) => {
  rememberTitleDraft("model", event.currentTarget.value, state.model || "gpt-5-nano");
  event.currentTarget.dataset.dirty = String(event.currentTarget.value !== (state.model || "gpt-5-nano"));
  updateModelApplyButton();
});

$("model").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  applyWritingModel();
});

$("model-apply").addEventListener("click", applyWritingModel);

$("paper-title").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  const editor = state.title_editor || {};
  rememberTitleDraft("title", event.currentTarget.value, editor.candidate || editor.current_title || "");
  $("title-status").textContent = studioT("标题有未保存修改。", "Title has unsaved changes.");
  updateTitleSaveButton();
});

$("title-gpt-prompt").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  rememberTitleDraft("prompt", event.currentTarget.value, (state.title_editor || {}).prompt || "");
});

$("title-generate").onclick = async () => {
  if (titleBusy) return;
  const prompt = $("title-gpt-prompt").value.trim();
  try {
    setTitleBusy(true, studioT("正在生成标题候选；不会自动保存…", "Generating title candidates; will not auto save…"));
    const payload = await request("/api/title/generate", {
      method: "POST",
      body: JSON.stringify({
        prompt: prompt || "Generate one concise, specific academic title that reflects the paper's actual problem and contribution. Do not add unsupported claims.",
        current_title: $("paper-title").value.trim(),
        model: $("model").value.trim(),
      }),
    });
    state = payload.state;
    forgetTitleDraft("title");
    forgetTitleDraft("prompt");
    $("paper-title").dataset.dirty = "false";
    $("title-gpt-prompt").dataset.dirty = "false";
    renderTitleEditor(true);
  } catch (error) {
    $("title-status").textContent = error.message;
    $("title-status").classList.add("error");
  } finally {
    setTitleBusy(false);
  }
};

$("title-save").onclick = async () => {
  if (titleBusy) return;
  const title = $("paper-title").value.trim();
  try {
    setTitleBusy(true, studioT("正在写入 LaTeX 并编译 PDF…", "Writing LaTeX and compiling PDF."));
    const payload = await request("/api/title/save", {
      method: "POST",
      body: JSON.stringify({title}),
    });
    state = payload.state;
    forgetTitleDraft("title");
    $("paper-title").dataset.dirty = "false";
    renderTitleEditor(true);
    renderPdf();
  } catch (error) {
    $("title-status").textContent = error.message;
    $("title-status").classList.add("error");
  } finally {
    setTitleBusy(false);
  }
};

async function acceptCurrent() {
  if (acceptRequestBusy) return;
  acceptRequestBusy = true;
  setBusy(true, studioT("正在核对最新段落状态…", "Verifying latest paragraph status…"));
  const requestedSection = activeSection;
  let acceptedParagraphId = "";
  let acceptanceCompleted = false;
  try {
    let paragraph = state.sections[requestedSection].current_paragraph;
    let candidate = paragraph && paragraph.candidate;
    const visibleParagraphId = paragraph && paragraph.id;
    const visibleCandidateText = $("candidate").value.trim();
    const visibleBaseText = proseBaselineText.trim();
    const latestState = normalizeStateUrls(await request("/api/state"));
    const latestParagraph = latestState.sections[requestedSection].current_paragraph;
    const latestCandidate = latestParagraph && latestParagraph.candidate;
    if (
      visibleParagraphId
      && latestParagraph
      && latestParagraph.id !== visibleParagraphId
    ) {
      state = latestState;
      $("candidate").dataset.dirty = "false";
      render();
      showMessage(studioT(`当前编辑位置已更新到 ${latestParagraph.id}，请确认后再 Accept。`, `Current editing position updated to ${latestParagraph.id}, Please confirm before Accept.`), true);
      return;
    }
    if (
      visibleParagraphId
      && latestParagraph
      && latestParagraph.id === visibleParagraphId
      && candidate
      && latestCandidate
      && candidate.id !== latestCandidate.id
      && visibleCandidateText !== String(latestCandidate.text || "").trim()
    ) {
      state = latestState;
      forgetProseDraft(`${requestedSection}:${visibleParagraphId}`);
      $("candidate").dataset.dirty = "false";
      render();
      showMessage(studioT("候选已在另一轮生成中更新；已自动载入最新版，请确认内容后再次 Accept。", "The candidate has been updated in another round of generation; the latest version is auto-loaded; please review and Accept again."), true);
      return;
    }
    state = latestState;
    paragraph = latestParagraph;
    candidate = latestCandidate;
    const manualRevision = Boolean(
      paragraph
      && visibleCandidateText
      && visibleCandidateText !== visibleBaseText
    );
    if (!candidate && !manualRevision) {
      render();
      showMessage(
        latestParagraph && visibleParagraphId && latestParagraph.id !== visibleParagraphId
          ? studioT(`当前编辑位置已更新到 ${latestParagraph.id}，请确认后再 Accept。`, `Current editing position updated to ${latestParagraph.id}, Please confirm before Accept.`)
          : studioT("当前段落没有可接受的正文。", "The current paragraph has no acceptable body text."),
        true,
      );
      return;
    }
    const revisingAccepted = Boolean(paragraph.accepted_text);
    acceptedParagraphId = paragraph.id;
    setBusy(true, studioT("正在校验引用；缺失时会联网检索、更新 BibTeX，再写入 LaTeX 并编译…", "Checking the paragraph, writing LaTeX, and compiling the PDF…"));
    const payload = await request("/api/accept", {
      method: "POST",
      body: JSON.stringify({
        section: requestedSection,
        paragraph_id: paragraph.id,
        candidate_id: candidate ? candidate.id : "",
        candidate_text: visibleCandidateText,
        base_text: visibleBaseText,
      }),
    });
    acceptanceCompleted = true;
    state = payload.state;
    forgetProseDraft(`${requestedSection}:${acceptedParagraphId}`);
    forgetCommentDraft(`${requestedSection}:${acceptedParagraphId}`);
    $("candidate").dataset.dirty = "false";
    if (activeSection === requestedSection) {
      const nextParagraph = state.sections[requestedSection].current_paragraph;
      render();
      showMessage(
        revisingAccepted
          ? studioT(`${acceptedParagraphId} 的新版本已替换写入 LaTeX，并完成 PDF 编译。`, `${acceptedParagraphId} The new version has replaced content in LaTeX and completed PDF compilation.`)
          : state.sections[requestedSection].complete
          ? studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译；当前 section 已完成。`, `${acceptedParagraphId} LaTeX compilation has been accepted and completed; the current section is finished.`)
          : nextParagraph
          ? studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译；正在后台准备 ${nextParagraph.id} 候选。`, `${acceptedParagraphId} LaTeX compilation has been accepted and completed; preparing in the background. ${nextParagraph.id} Candidate.`)
          : studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译。`, `${acceptedParagraphId} LaTeX compilation completed.`),
      );
      if (
        !revisingAccepted
        && nextParagraph
        && !nextParagraph.candidate
        && !nextParagraph.accepted_text
      ) {
        const key = `${requestedSection}:${nextParagraph.id}`;
        autoAttempted.add(key);
        setBusy(
          true,
          studioT(`${acceptedParagraphId} 已写入并编译；正在生成 ${nextParagraph.id}…`, `${acceptedParagraphId} Written and compiled; generating. ${nextParagraph.id}…`),
        );
        const nextPayload = await request("/api/generate", {
          method: "POST",
          body: JSON.stringify({
            section: requestedSection,
            paragraph_id: nextParagraph.id,
            model: $("model").value.trim(),
            current_text: "",
            comment: "",
          }),
        });
        state = nextPayload.state;
      }
      render();
      const current = state.sections[requestedSection].current_paragraph;
      showMessage(
        revisingAccepted
          ? studioT(`${acceptedParagraphId} 的新版本已替换写入 LaTeX，并完成 PDF 编译。`, `${acceptedParagraphId} The new version has replaced content in LaTeX and completed PDF compilation.`)
          : state.sections[requestedSection].complete
          ? studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译；当前 section 已完成。`, `${acceptedParagraphId} LaTeX compilation has been accepted and completed; the current section is finished.`)
          : current
          ? studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译；${current.id} 候选已刷新。`, `${acceptedParagraphId} LaTeX compilation completed;${current.id} Candidate refreshed.`)
          : studioT(`${acceptedParagraphId} 已接受并完成 LaTeX 编译。`, `${acceptedParagraphId} LaTeX compilation completed.`),
      );
    } else {
      renderSections();
      showMessage(studioT(`${state.sections[requestedSection].title} 已接受并完成 LaTeX 编译。`, `${state.sections[requestedSection].title} LaTeX compilation completed.`));
    }
  } catch (error) {
    if (acceptanceCompleted) {
      render();
      showMessage(
        studioT(`${acceptedParagraphId} 已写入 LaTeX 并编译，但下一段生成失败：${error.message}`, `${acceptedParagraphId} LaTeX has been written and compiled, but generation of the next paragraph failed.${error.message}`),
        true,
      );
    } else {
      showMessage(error.message, true);
    }
  } finally {
    acceptRequestBusy = false;
    setBusy(false);
  }
}

$("accept").addEventListener("click", acceptCurrent);

$("compile").onclick = async () => {
  if (compileRequestBusy) return;
  compileRequestBusy = true;
  try {
    setBusy(true, studioT("正在编译 LaTeX…", "Compiling LaTeX…"));
    const payload = await request("/api/compile", {method: "POST", body: "{}"});
    state = payload.state;
    showMessage(studioT("PDF 编译成功。", "PDF Compilation succeeded."));
    renderPdf();
  } catch (error) {
    showMessage(error.message, true);
    try {
      await refresh();
    } catch (refreshError) {
      showMessage(studioT(`${error.message}\n状态刷新也失败：${refreshError.message}`, `${error.message}\nStatus refresh also failed:${refreshError.message}`), true);
    }
  } finally {
    compileRequestBusy = false;
    setBusy(false);
  }
};

async function submitGeneratedReset(typed) {
  if (generatedResetBusy) return;
  const requestedModel = $("model").value.trim();
  const projectId = state && state.project && state.project.id;
  if (typed.trim() !== projectId) {
    $("reset-project-copy-status").textContent = studioT("项目 ID 不匹配；未删除任何生成内容。", "Project ID mismatch; no generated content was deleted.");
    $("reset-project-copy-status").classList.add("error");
    $("reset-project-confirm").focus();
    $("reset-project-confirm").select();
    return;
  }
  generatedResetBusy = true;
  $("reset-generated-dialog").close();
  try {
    setBusy(true, studioT("正在清空生成内容并编译空壳 PDF…", "Clearing generated content and compiling an empty shell PDF."));
    // Cancel old vector-page loads before the server removes generated page
    // caches and recompiles the empty shell. Otherwise an already queued
    // page-4 request can race the new one-page PDF and surface a noisy 400.
    $("pdf-pages").replaceChildren();
    $("pdf-pages").dataset.signature = "";
    $("pdf-navigation").replaceChildren();
    $("pdf-navigation").dataset.signature = "";
    $("pdf-viewer").hidden = true;
    $("pdf-download").hidden = true;
    updatePdfPageIndicator();
    const payload = await request("/api/reset-generated-paper", {
      method: "POST",
      body: JSON.stringify({project_id: typed.trim(), model: requestedModel}),
    });
    state = payload.state;
    clearBrowserDraftsForProject(projectId);
    activeSection = state.sections.abstract ? "abstract" : Object.keys(state.sections)[0];
    activeView = "writing";
    autoAttempted.clear();
    autoFigurePromptAttempted.clear();
    autoDataPanelAttempted.clear();
    autoTableGenerateAttempted.clear();
    render();
    showMessage(payload.message);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    generatedResetBusy = false;
    setBusy(false);
  }
}

$("reset-generated").onclick = () => {
  const projectId = state && state.project && state.project.id;
  if (!projectId) {
    showMessage(studioT("当前没有可清空的论文项目。", "There is no paper project to clear currently."), true);
    return;
  }
  $("reset-project-id").value = projectId;
  $("reset-project-confirm").value = "";
  $("reset-project-copy-status").textContent = "";
  $("reset-project-copy-status").classList.remove("error");
  $("reset-generated-dialog").showModal();
  $("reset-project-id").focus();
  $("reset-project-id").select();
};

$("reset-project-copy").onclick = async () => {
  const input = $("reset-project-id");
  let copied = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(input.value);
      copied = true;
    }
  } catch (_error) {
    copied = false;
  }
  if (!copied) {
    input.focus();
    input.select();
    try {
      copied = document.execCommand("copy");
    } catch (_error) {
      copied = false;
    }
  }
  input.focus();
  input.select();
  $("reset-project-copy-status").classList.toggle("error", !copied);
  $("reset-project-copy-status").textContent = copied
    ? studioT("项目 ID 已复制。", "Project ID has been copied.")
    : studioT("自动复制失败；ID 已选中，请按 Ctrl/Cmd+C。", "Auto copy failed; the ID has been selected, please press Ctrl/Cmd+C.");
};

function closeGeneratedResetDialog() {
  $("reset-generated-dialog").close();
}

$("reset-generated-close").onclick = closeGeneratedResetDialog;
$("reset-generated-cancel").onclick = closeGeneratedResetDialog;
$("reset-generated-confirm").onclick = () => {
  submitGeneratedReset($("reset-project-confirm").value);
};
$("reset-project-confirm").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    submitGeneratedReset($("reset-project-confirm").value);
  }
});

function switchView(view) {
  if (!state || !state.sections) return;
  activeView = view;
  if (["figures", "tables"].includes(view)) {
    const paragraph = state.sections[activeSection].current_paragraph;
    const desiredKind = view === "tables" ? "table" : "figure";
    const related = (paragraph && paragraph.artifacts || []).find(
      (artifact) => artifact.kind === desiredKind,
    );
    let available = sectionFigures();
    if (!available.length) {
      const collection = view === "tables" ? (state.tables || []) : (state.figures || []);
      // Public figure records use concrete kinds such as mechanism/data rather
      // than the paragraph-binding kind "figure". Pick the first record from
      // the already view-specific collection when the active section has none.
      const fallback = collection[0] || null;
      const fallbackSection = fallback && (
        (fallback.source_sections || [])[0]
        || Object.keys(fallback.related_paragraphs || {})[0]
      );
      if (fallbackSection && state.sections[fallbackSection]) {
        activeSection = fallbackSection;
        available = sectionFigures();
      }
    }
    const selected = related
      ? available.find((artifact) => artifact.id === related.id)
      : null;
    const first = selected || available[0];
    if (first) activeFigure = first.id;
  }
  render();
}

$("writing-view").onclick = () => switchView("writing");
async function startSectionDraftFromBrowser(section = activeSection) {
  if (fullDraftRequestBusy || queuedSectionDraftStart) return;
  const requestedSection = section;
  if (proseRequestBusy) {
    queuedSectionDraftStart = requestedSection;
    render();
    showMessage(studioT(`${state.sections[requestedSection].title} 已加入队列；当前段落生成完成后会自动开始整节生成。`, `${state.sections[requestedSection].title} Queued; once the current paragraph generation is complete, the entire section generation will automatically start.`));
    return;
  }
  fullDraftRequestBusy = true;
  $("section-draft-start").disabled = true;
  try {
    const payload = await request("/api/section-draft/start", {
      method: "POST",
      body: JSON.stringify({
        model: $("model").value.trim(),
        section: requestedSection,
      }),
    });
    state = payload.state;
    render();
    showMessage(studioT(`${state.sections[requestedSection].title} 的整节生成任务已启动；将按段落顺序自动写入 LaTeX 并编译。`, `${state.sections[requestedSection].title} The entire section generation task has started; LaTeX will be written and compiled automatically in paragraph order.`));
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    fullDraftRequestBusy = false;
    render();
  }
}
$("section-draft-start").onclick = () => startSectionDraftFromBrowser();
$("figures-view").onclick = () => switchView("figures");
$("tables-view").onclick = () => switchView("tables");

async function runFigureAction(path, body, busyMessage) {
  if (figureRequestBusy) return null;
  figureRequestBusy = true;
  const requestedArtifactId = body.figure_id || body.table_id || "";
  updateFigureButtonStates();
  try {
    $("figure-message").classList.remove("error");
    $("figure-gate").classList.remove("show");
    setBusy(true, busyMessage);
    $("figure-message").textContent = busyMessage;
    const payload = await request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state = payload.state;
    render();
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").classList.remove("error");
      $("figure-message").textContent = payload.message || studioT("完成。", "Done.");
    }
    return payload;
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
      $("figure-gate").textContent = error.message;
      $("figure-gate").classList.add("show");
    }
    return null;
  } finally {
    figureRequestBusy = false;
    setBusy(false);
    const current = selectedFigure();
    if (current && activeView === "figures" && current.kind === "data") {
      setTimeout(() => scheduleAutomaticDataPanel(current), 0);
    } else if (current && activeView === "tables" && current.kind === "table") {
      setTimeout(() => scheduleAutomaticTableGenerate(current), 0);
    }
  }
}

async function startFigureJob(path, body, startingMessage) {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const requestedArtifactId = body.figure_id || body.table_id || "";
  updateFigureButtonStates();
  try {
    $("figure-message").classList.remove("error");
    $("figure-message").textContent = startingMessage;
    const payload = await request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state = payload.state;
    render();
    ensureFigurePolling();
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
    const current = selectedFigure();
    if (current && activeView === "figures" && current.kind === "data") {
      setTimeout(() => scheduleAutomaticDataPanel(current), 0);
    } else if (current && activeView === "tables" && current.kind === "table") {
      setTimeout(() => scheduleAutomaticTableGenerate(current), 0);
    }
  }
}

async function pollFigureJobs() {
  figurePollTimer = null;
  try {
    state = normalizeStateUrls(await request("/api/state"));
    render();
  } catch (error) {
    if (["figures", "tables"].includes(activeView)) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
  } finally {
    ensureFigurePolling();
  }
}

function ensureFigurePolling() {
  const running = [...(state.figures || []), ...(state.tables || [])].some(figureIsRunning);
  if (running && !figurePollTimer) {
    figurePollTimer = setTimeout(pollFigureJobs, 1000);
  } else if (!running && figurePollTimer) {
    clearTimeout(figurePollTimer);
    figurePollTimer = null;
  }
}

$("figure-prompt").onclick = () => startFigureJob(
  "/api/figure/prompt",
  {
    figure_id: activeFigure,
    current_prompt: $("draw-prompt").value,
    prompt_instruction: $("prompt-instruction").value,
  },
  studioT("正在启动画图 Prompt 生成…", "Starting drawing-prompt generation…"),
);

$("figure-draw").onclick = () => startFigureJob(
  "/api/figure/draw",
  {figure_id: activeFigure, draw_prompt: $("draw-prompt").value},
  studioT("正在检查 Prompt 是否变化…", "Checking if the Prompt has changed…"),
);

$("draw-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, "draw_prompt", event.currentTarget.value, figure.draw_prompt || "");
  }
  updateFigureButtonStates();
});

$("prompt-instruction").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(
      figure.id,
      "prompt_instruction",
      event.currentTarget.value,
      figure.prompt_instruction || "",
    );
  }
  updateFigureButtonStates();
});

$("figure-cancel").onclick = async () => {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const button = $("figure-cancel");
  updateFigureButtonStates();
  $("figure-message").classList.remove("error");
  $("figure-message").textContent = studioT("正在停止本次 Codex 绘图任务…", "Stopping this Codex drawing task…");
  try {
    const result = await request("/api/figure/cancel", {
      method: "POST",
      body: JSON.stringify({figure_id: activeFigure}),
    });
    state = result.state;
    render();
  } catch (error) {
    $("figure-message").textContent = error.message;
    $("figure-message").classList.add("error");
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
    ensureFigurePolling();
  }
};

$("figure-build").onclick = () => startFigureJob(
  "/api/figure/build",
  {figure_id: activeFigure},
  studioT("正在启动本地 Agent，按草图重建原生 PowerPoint shapes…", "Starting local Agent and reconstructing original PowerPoint shapes according to the sketch."),
);

$("mechanism-preview-toggle").onclick = () => {
  const figure = selectedFigure();
  if (
    !figure
    || figure.status === "approved"
    || !figure.gpt_preview_url
    || !figure.paper_preview_url
  ) return;
  const current = mechanismPreviewModes.get(figure.id) || "paper";
  mechanismPreviewModes.set(figure.id, current === "paper" ? "gpt" : "paper");
  renderFigures();
};

function updateFigurePlacement() {
  const figure = selectedFigure();
  return runFigureAction(
    figure && figure.kind === "table"
      ? "/api/table/placement"
      : "/api/figure/placement",
    figure && figure.kind === "table"
      ? {
          table_id: activeFigure,
          placement_after: $("figure-placement").value,
          layout_mode: $("figure-layout-mode").value,
        }
      : {
          figure_id: activeFigure,
          placement_after: $("figure-placement").value,
          layout_mode: $("figure-layout-mode").value,
        },
    figure && figure.kind === "table"
      ? studioT("正在更新表格位置与单栏/双栏排版并重新编译 PDF…", "Updating table position and single column or double column layout, and recompiling PDF…")
      : studioT("正在更新插图位置与排版方式…", "Updating figure locations and layout settings…"),
  );
}

$("figure-placement").onchange = updateFigurePlacement;
$("figure-layout-mode").onchange = updateFigurePlacement;

$("figure-caption").addEventListener("input", (event) => {
  const figure = selectedFigure();
  const dirty = Boolean(figure && event.currentTarget.value !== (figure.caption || ""));
  event.currentTarget.dataset.dirty = String(dirty);
  if (figure && dirty) rememberCaptionDraft(figure.id, event.currentTarget.value);
  else if (figure) forgetCaptionDraft(figure.id);
  $("figure-caption-status").textContent = dirty
    ? (figure && figure.status === "approved"
      ? studioT("Caption 已修改，尚未更新到正文与 PDF", "Caption Modified, not yet updated in the main text and PDF.")
      : studioT("Caption 已修改，尚未保存", "Caption Modified, not yet saved"))
    : (figure && figure.status === "approved"
      ? studioT("Caption 已写入正文与 PDF", "Caption Written into main text and PDF")
      : studioT("当前正文将使用此 Caption", "The current main text will use this caption."));
  updateFigureButtonStates();
});

$("figure-caption-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, "caption_prompt", event.currentTarget.value, "");
  }
});

$("figure-caption-generate").onclick = async () => {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const requestedFigureId = activeFigure;
  const button = $("figure-caption-generate");
  const captionInput = $("figure-caption");
  const originalLabel = button.textContent;
  try {
    updateFigureButtonStates();
    button.textContent = studioT("正在生成 Caption…", "Generating caption…");
    $("figure-caption-status").textContent = studioT("正在生成 Caption candidate…", "Generating Caption candidate.");
    const payload = await request("/api/figure/caption/generate", {
      method: "POST",
      body: JSON.stringify({
        figure_id: requestedFigureId,
        current_caption: captionInput.value,
        prompt_instruction: $("figure-caption-prompt").value,
      }),
    });
    const generatedCaption = payload.caption || "";
    const requestedFigure = (state.figures || []).find((item) => item.id === requestedFigureId);
    const dirty = Boolean(requestedFigure && generatedCaption !== (requestedFigure.caption || ""));
    if (dirty) rememberCaptionDraft(requestedFigureId, generatedCaption);
    else forgetCaptionDraft(requestedFigureId);
    forgetFigureEditorDraft(requestedFigureId, "caption_prompt");
    const figure = selectedFigure();
    if (!figure || figure.id !== requestedFigureId) return;
    captionInput.value = generatedCaption;
    $("figure-caption-prompt").value = "";
    $("figure-caption-prompt").dataset.dirty = "false";
    captionInput.dataset.dirty = String(dirty);
    $("figure-caption-status").textContent = dirty
      ? studioT("模型 candidate 尚未保存", "Model candidate not saved yet")
      : studioT("模型 candidate 与当前 Caption 相同", "Model candidate is the same as the current caption.");
    updateFigureButtonStates();
  } catch (error) {
    $("figure-caption-status").textContent = error.message;
    showMessage(error.message, true);
  } finally {
    figureRequestBusy = false;
    button.textContent = originalLabel;
    updateFigureButtonStates();
  }
};

async function saveFigureCaption() {
  if (figureRequestBusy) return false;
  figureRequestBusy = true;
  const requestedFigureId = activeFigure;
  const input = $("figure-caption");
  const requestedCaption = input.value;
  try {
    updateFigureButtonStates();
    const payload = await request("/api/figure/caption", {
      method: "POST",
      body: JSON.stringify({figure_id: requestedFigureId, caption: requestedCaption}),
    });
    state = payload.state;
    forgetCaptionDraft(requestedFigureId);
    if (input.dataset.figureId === requestedFigureId && input.value === requestedCaption) {
      input.dataset.dirty = "false";
    }
    render();
    if (selectedFigure() && selectedFigure().id === requestedFigureId) {
      $("figure-message").textContent = payload.message || studioT("Caption 已保存。", "Caption Saved.");
      $("figure-message").classList.remove("error");
    }
    return true;
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedFigureId) {
      $("figure-caption-status").textContent = studioT(`Caption 保存失败：${error.message}`, `Caption Save failed:${error.message}`);
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
    return false;
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
  }
}

$("figure-caption-save").onclick = saveFigureCaption;

async function approveFigureOrSaveCaption() {
  const figure = selectedFigure();
  const requestedFigureId = figure && figure.id;
  const dirty = $("figure-caption").dataset.dirty === "true";
  if (dirty) {
    const saved = await saveFigureCaption();
    if (!saved || (figure && figure.status === "approved")) return;
  }
  return runFigureAction(
    "/api/figure/approve",
    {figure_id: requestedFigureId},
    studioT("正在插入正文、补充 Figure 引用并重新编译 PDF…", "Inserting the body text, adding Figure references, and recompiling the PDF."),
  );
}

$("figure-approve").onclick = approveFigureOrSaveCaption;

$("data-compose").onclick = () => runFigureAction(
  "/api/figure/compose",
  {
    figure_id: activeFigure,
    layout_prompt: $("data-layout-prompt").value,
    layout_width: $("figure-layout-mode").value === "two-column"
      ? "two-column"
      : "single-column",
  },
  studioT("本地 Agent 正在解释组合 Prompt；随后将在 PPT 中排版并导出、裁剪 PDF…", "Starting local Agent and reconstructing original PowerPoint shapes according to the sketch."),
);

function openRuntimeKeyDialog() {
  const dialog = $("runtime-key-dialog");
  $("runtime-key-message").textContent = "";
  $("runtime-key-provider").value = state.llm_provider || "openai";
  if (!dialog.open) dialog.showModal();
  setTimeout(() => $("runtime-key-input").focus(), 0);
}

function closeRuntimeKeyDialog() {
  $("runtime-key-input").value = "";
  $("runtime-key-dialog").close();
}

$("runtime-key-open").onclick = openRuntimeKeyDialog;
$("runtime-key-close").onclick = closeRuntimeKeyDialog;
$("runtime-key-cancel").onclick = closeRuntimeKeyDialog;
$("runtime-key-dialog").addEventListener("click", (event) => {
  if (event.target === $("runtime-key-dialog")) closeRuntimeKeyDialog();
});
$("runtime-key-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = $("runtime-key-submit");
  const status = $("runtime-key-message");
  submit.disabled = true;
  status.textContent = studioT("正在安全更新…", "Security update in progress…");
  try {
    const payload = await request("/api/runtime-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: $("runtime-key-provider").value,
        api_key: $("runtime-key-input").value,
      }),
    });
    $("runtime-key-input").value = "";
    state = payload.state;
    render();
    $("runtime-key-dialog").close();
  } catch (error) {
    $("runtime-key-input").value = "";
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
$("data-layout-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(
      figure.id,
      "layout_prompt",
      event.currentTarget.value,
      figure.layout_prompt || "",
    );
  }
});

$("single-data-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure && (figure.panels || []).length) {
    const panel = figure.panels[0];
    rememberFigureEditorDraft(
      figure.id,
      `panel:${panel.id}`,
      event.currentTarget.value,
      panel.agent_prompt || "",
    );
  }
});

function rememberTableEditorDraft(event, field, canonicalValue) {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, field, event.currentTarget.value, canonicalValue);
  }
}

$("table-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_generation_prompt", (figure && figure.generation_prompt) || "");
});

$("table-agent-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_agent_prompt", (figure && figure.agent_prompt) || "");
});

$("table-latex").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_latex", (figure && figure.latex) || "");
  updateFigureButtonStates();
});

$("data-approve").onclick = approveFigureOrSaveCaption;

$("table-generate").onclick = () => runFigureAction(
  "/api/table/generate",
  {
    table_id: activeFigure,
    generation_prompt: $("table-prompt").value,
  },
  studioT("正在启动本地 Agent 从可追溯结果生成表格初稿…", "Starting local Agent to generate the initial draft table from traceable results…"),
);

$("table-agent-edit").onclick = () => startFigureJob(
  "/api/table/agent-edit",
  {
    table_id: activeFigure,
    latex: $("table-latex").value,
    agent_prompt: $("table-agent-prompt").value,
  },
  studioT("正在启动本机 Codex agent 修改表格…", "Starting local Codex agent to modify the table."),
);

$("table-save").onclick = () => runFigureAction(
  "/api/table/save",
  {table_id: activeFigure, latex: $("table-latex").value},
  studioT("正在保存表格修改…", "Saving table edits…"),
);

$("table-approve").onclick = () => runFigureAction(
  "/api/table/approve",
  {table_id: activeFigure, latex: $("table-latex").value},
  studioT("正在插入正文并重新编译 PDF…", "Inserting main text and recompiling PDF…"),
);

refresh().catch((error) => {
  $("section-title").textContent = studioT("加载失败", "Loading failed");
  $("load-error-message").textContent = error.message;
  $("load-error").hidden = false;
  [
    "model", "model-apply", "reset-generated", "writing-view",
    "figures-view", "tables-view", "compile", "section-draft-start",
    "runtime-key-open",
  ].forEach((id) => {
    const control = $(id);
    if (control) control.disabled = true;
  });
  $("writing-workspace").hidden = true;
  $("figures-workspace").hidden = true;
});
