"""Strict contracts between Architect, Coder, Tester, and Reviewer."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rationale: str = Field(min_length=3, max_length=500)
    tasks: list[str] = Field(min_length=1, max_length=6)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=3, max_length=300)
    files: dict[str, str] = Field(min_length=1, max_length=6)


class TestResult(BaseModel):
    passed: bool
    exit_code: int
    output: str


class AgentState(TypedDict, total=False):
    issue_number: int
    issue_title: str
    issue_body: str
    workspace: Path
    attempt: int
    max_repairs: int
    plan: Plan
    files: dict[str, str]
    test: TestResult
    status: str
    trace: list[str]
    publish: bool
    pr_url: str
