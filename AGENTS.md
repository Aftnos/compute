# AGENTS.md

## 项目概述
- 项目名称：Windows 桌面自动化工具（Python）
- 目标：通过低代码（PyQt6 UI）配置并执行浏览器网页相关的键盘/鼠标自动化流程；支持全局热键与定时触发；提供紧急停止。
- 平台与范围：仅 Windows 10/11；不做跨平台适配（除非任务明确要求）。

## 合规与安全边界（必须遵守）
- 本项目需要实现自动化按键控制（填写表单、点击、滚动、切换焦点、自动键盘、自动鼠标、chrome浏览器自动化控制(通过python)）。
- 在编写完新功能时，请务必在此文件中添加跟新说明和更新过时的说明。

## 语言要求
- 简体中文语言
- 语言环境：UTF-8
- 注释：使用简体中文注释，使用中文文档。
- PR使用中文进行描述。

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
  - 配置使用 JSON（人可读、可导入导出）。

## 日志与可观测性
- 每次运行生成 Run 记录：start/end、trigger 来源、status、steps 日志（开始/结束/耗时/结果/错误）。
- 日志需可导出（JSONL 或 JSON）。

## 本地运行（占位，按仓库实际文件名调整）
- 建议命令：
  - python -m venv .venv
  - .venv\Scripts\activate
  - pip install -r requirements.txt
  - python -m app
- 测试：
  - pytest -q

## 更新记录
- 2026-01-12--v0.0.1：初始化项目。
- 2026-01-12--v0.0.2：中文化本项目。
- 2026-01-13--v0.1.0：新增低代码流程编辑、更多动作类型与浏览器自动化支持。
