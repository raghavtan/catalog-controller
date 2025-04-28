from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime

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
    # Add other fields as needed

class KubernetesCondition(BaseModel):
    type: str
    status: str # "True", "False", "Unknown"
    lastTransitionTime: str
    reason: str
    message: str

class ParentResource(BaseModel):
    apiVersion: str
    kind: str
    metadata: KubernetesMetadata
    spec: Dict[str, Any]
    status: Optional[Dict[str, Any]] = Field(default_factory=dict)

# Metacontroller Request Structure for Sync and Finalize hooks
class MetacontrollerRequest(BaseModel):
    controller: Dict[str, Any] # The CompositeController object itself
    parent: ParentResource
    children: Dict[str, Dict[str, Any]] = Field(default_factory=dict) # Child objects by Kind.apiVersion -> name/namespace/name
    related: Dict[str, Dict[str, Any]] = Field(default_factory=dict) # Related objects by Kind.apiVersion -> name/namespace/name
    finalizing: bool # True if this is a finalize hook call

# Metacontroller Response Structure for Sync hook
class SyncResponse(BaseModel):
    status: Dict[str, Any] = Field(default_factory=dict) # Desired status for the parent
    children: List[Dict[str, Any]] = Field(default_factory=list) # Desired list of child objects (flat list)
    resyncAfterSeconds: Optional[float] = None # Optional one-time resync request

# Metacontroller Response Structure for Finalize hook
class FinalizeResponse(BaseModel):
    status: Dict[str, Any] = Field(default_factory=dict) # Desired status for the parent
    children: List[Dict[str, Any]] = Field(default_factory=list) # Desired list of child objects (flat list)
    finalized: bool # Indicates if finalization is complete
    resyncAfterSeconds: Optional[float] = None # Optional one-time resync request

class ResourceKind(str, Enum):
    COMPONENT = "components"
    SCORECARD = "scorecards"
    METRIC = "metrics"