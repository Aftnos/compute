# AGENTS.md

## 项目概述
- 项目名称：Windows 桌面自动化工具（Python）
- 目标：通过低代码（PyQt6 UI）配置并执行浏览器网页相关的键盘/鼠标自动化流程；支持全局热键与定时触发；提供紧急停止。
- 平台与范围：仅 Windows 10/11；不做跨平台适配（除非任务明确要求）。

## 合规与安全边界（必须遵守）
- 本项目只实现“用户本可手动完成的重复操作”的自动化按键控制（填写表单、点击、滚动、切换焦点、自动键盘、自动鼠标等）。

## 代码与架构约定
- 语言：Python 3.10+；强制使用类型标注（public API 至少要有 type hints）。
- GUI：PyQt6。
  - UI 线程不得执行阻塞任务（禁止在主线程直接 sleep/长循环/等待 I/O）。
  - 流程执行引擎必须运行在工作线程（QThread/QRunnable/QThreadPool 皆可），与 UI 通过 signals/slots 通信。
- 推荐分层（如目录不同，可按概念保持一致）：
  - app/ui/         PyQt6 界面与交互
  - app/engine/     Runner、停止控制、状态机、错误处理
  - app/actions/    动作实现（键盘、鼠标、等待、聚焦窗口等）
  - app/triggers/   全局热键、定时调度
  - app/models/     Flow/Step/Trigger/Run 数据模型（建议 pydantic 或 dataclasses）
  - app/storage/    JSON 配置读写、迁移、导入导出
  - app/logging/    运行日志与导出
- 数据持久化：
  - Flow 配置使用 JSON（人可读、可导入导出）。
  - 不保存敏感信息（如用户密码/证件号）为明文；若未来需要，需单独设计加密与输入机制，并在任务中明确说明。

## 动作（Actions）实现规范
- MVP 动作集（优先实现）：
  - TypeText(text, mode=key_in|paste, interval_ms?)
  - KeyPress(key)
  - Hotkey(keys[])
  - Click(x,y, button=left|right, clicks=1|2)
  - Scroll(delta, x?, y?)
  - Wait(ms)
  - FocusWindow(title_contains?|process_name?)（可选但推荐）
- 坐标/焦点风险：
  - 默认认为“焦点窗口正确”，但需提供可选的 FocusWindow 步骤与 require_window_focus 选项。
  - 所有输入类动作执行前后写入步骤级日志（包含参数摘要，但不记录敏感文本全文）。

## 触发器（Triggers）实现规范
- 全局热键：
  - 每个 Flow 可绑定 0..1 个热键；检测冲突并提示，不允许静默覆盖。
  - 全局“紧急停止热键”必须存在（默认可设 Ctrl+Alt+Esc），触发后尽快停止当前 Run。
- 定时触发：
  - 支持 daily/weekly/cron 三类；MVP 不做“错过补跑”，除非任务明确要求。

## 停止与错误处理
- 停止模型：软停止（StopRequested），在步骤边界尽快中断，不强杀进程。
- 错误策略（MVP）：
  - 任一步骤异常 => Run 标记 Failed，记录错误详情与失败步骤索引。
  - 不实现复杂分支/循环/重试，除非任务明确要求（后续可扩展）。

## 日志与可观测性
- 每次运行生成 Run 记录：start/end、trigger 来源、status、steps 日志（开始/结束/耗时/结果/错误）。
- 日志需可导出（JSONL 或 JSON）。

## 开发流程（对代码代理的工作协议）
- 开工前：
  - 先用 3-6 行概述“将改哪些文件、为什么、如何验证”。
  - 若需要新增依赖（pip 包），必须先征求确认并说明用途与替代方案。
- 开发中：
  - 改动尽量小且可回滚；避免无关重构。
  - 遵守模块边界：UI 不直接调用系统输入；统一经 engine/actions 层。
- 交付前（Definition of Done）：
  - 代码可运行（至少提供一个最小 demo Flow 或示例配置）。
  - 关键路径有基础测试（至少模型校验/调度解析/停止控制的单元测试）。
  - 更新必要的 README/注释（特别是风险提示与合规边界）。

## 本地运行（占位，按仓库实际文件名调整）
- 建议命令：
  - python -m venv .venv
  - .venv\Scripts\activate
  - pip install -r requirements.txt
  - python -m app
- 测试：
  - pytest -q
