"""Validated API request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnswerType = Literal["short_text", "long_text", "number", "date", "multiple_choice", "yes_no", "custom_text"]


class QuestionInput(BaseModel):
    question_number: int = Field(ge=1)
    question_text: str = Field(min_length=1, max_length=4000)
    answer_type: AnswerType = "short_text"
    is_required: bool = False
    display_order: int = Field(ge=0)
    page_number: int = Field(default=1, ge=1)
    region_x: float | None = Field(default=None, ge=0, le=1)
    region_y: float | None = Field(default=None, ge=0, le=1)
    region_width: float | None = Field(default=None, gt=0, le=1)
    region_height: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_region(self):
        coords = (self.region_x, self.region_y, self.region_width, self.region_height)
        if any(value is not None for value in coords) and any(value is None for value in coords):
            raise ValueError("All four region coordinates must be supplied together")
        if self.region_x is not None and self.region_x + self.region_width > 1:
            raise ValueError("Region extends past the right edge")
        if self.region_y is not None and self.region_y + self.region_height > 1:
            raise ValueError("Region extends past the bottom edge")
        return self


class QuestionCreate(QuestionInput):
    pass


class QuestionUpdate(BaseModel):
    question_number: int | None = Field(default=None, ge=1)
    question_text: str | None = Field(default=None, min_length=1, max_length=4000)
    answer_type: AnswerType | None = None
    is_required: bool | None = None
    display_order: int | None = Field(default=None, ge=0)
    page_number: int | None = Field(default=None, ge=1)
    region_x: float | None = Field(default=None, ge=0, le=1)
    region_y: float | None = Field(default=None, ge=0, le=1)
    region_width: float | None = Field(default=None, gt=0, le=1)
    region_height: float | None = Field(default=None, gt=0, le=1)


class QuestionRead(QuestionInput):
    model_config = ConfigDict(from_attributes=True)
    id: str


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10000)
    version: str = Field(default="1.0", max_length=40)
    page_count: int = Field(default=1, ge=1, le=100)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=10000)
    version: str | None = Field(default=None, max_length=40)
    page_count: int | None = Field(default=None, ge=1, le=100)


class TemplateRead(TemplateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionRead] = []
