from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class KubernetesMetadata(BaseModel):
    name: str
    namespace: Optional[str] = None
    uid: str
    resourceVersion: str
    generation: int
    creationTimestamp: Optional[datetime] = None
    deletionTimestamp: Optional[datetime] = None
    annotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)
    finalizers: Optional[List[str]] = Field(default_factory=list)


class KubernetesCondition(BaseModel):
    type: str
    status: str
    lastTransitionTime: str
    reason: str
    message: str


class ParentResource(BaseModel):
    apiVersion: str
    kind: str
    metadata: KubernetesMetadata
    spec: Dict[str, Any]
    status: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MetacontrollerRequest(BaseModel):
    controller: Dict[str, Any]
    parent: ParentResource
    children: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    related: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    finalizing: bool


class SyncResponse(BaseModel):
    status: Dict[str, Any] = Field(default_factory=dict)
    children: List[Dict[str, Any]] = Field(default_factory=list)
    resyncAfterSeconds: Optional[float] = None


class FinalizeResponse(BaseModel):
    status: Dict[str, Any] = Field(default_factory=dict)
    children: List[Dict[str, Any]] = Field(default_factory=list)
    finalized: bool
    resyncAfterSeconds: Optional[float] = None


class ResourceKind(str, Enum):
    COMPONENT = "components"
    SCORECARD = "scorecards"
    METRIC = "metrics"
