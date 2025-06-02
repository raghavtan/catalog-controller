```mermaid
graph TB
    subgraph "Enhanced Controller Flow"
        START[Controller Triggered] --> CHECK_STATUS{Status ID exists?}
        
        %% Branch 1: No Status ID - Check if exists by name
        CHECK_STATUS -->|No| CHECK_BY_NAME[GET /resource/by-name/{name}]
        CHECK_BY_NAME --> NAME_EXISTS{Resource exists<br/>by name?}
        NAME_EXISTS -->|Yes| IMPORT_ID[Import ID to K8s status]
        NAME_EXISTS -->|No| CREATE_NEW[POST /resource - Create New]
        
        %% Branch 2: Status ID exists - Validate and check for updates
        CHECK_STATUS -->|Yes| GET_BY_ID[GET /resource/{id}]
        GET_BY_ID --> ID_EXISTS{Resource exists<br/>by ID?}
        ID_EXISTS -->|No| CHECK_BY_NAME
        ID_EXISTS -->|Yes| COMPARE_SPEC{Spec differences<br/>detected?}
        
        %% Update flow
        COMPARE_SPEC -->|Yes| UPDATE_RESOURCE[PUT /resource/{id}]
        COMPARE_SPEC -->|No| SYNC_ASSOCIATIONS[Sync metric associations]
        
        %% Convergence points
        IMPORT_ID --> SYNC_ASSOCIATIONS
        CREATE_NEW --> SYNC_ASSOCIATIONS
        UPDATE_RESOURCE --> SYNC_ASSOCIATIONS
        
        %% Final steps
        SYNC_ASSOCIATIONS --> UPDATE_STATUS[Update K8s Status]
        UPDATE_STATUS --> TRIGGER_DEPENDENTS{Trigger dependent<br/>controllers?}
        TRIGGER_DEPENDENTS -->|Component changed| TRIGGER_SCORECARDS[Queue Scorecard reconciliation]
        TRIGGER_DEPENDENTS -->|Metric changed| TRIGGER_COMPONENTS[Queue Component reconciliation]
        TRIGGER_DEPENDENTS -->|Scorecard changed| TRIGGER_COMP_METRICS[Queue Component & Metric reconciliation]
        
        TRIGGER_SCORECARDS --> END[Complete]
        TRIGGER_COMPONENTS --> END
        TRIGGER_COMP_METRICS --> END
        TRIGGER_DEPENDENTS -->|No dependents| END
    end
    
    subgraph "Cascade Update Flow"
        METRIC_CHANGE[Metric Spec Changed] --> FIND_DEPENDENT_COMPS[Find Components using this Metric]
        FIND_DEPENDENT_COMPS --> UPDATE_COMP_ASSOCIATIONS[Update Component metric associations]
        UPDATE_COMP_ASSOCIATIONS --> FIND_DEPENDENT_SCORECARDS[Find Scorecards using this Metric]
        FIND_DEPENDENT_SCORECARDS --> UPDATE_SCORECARD_ASSOCIATIONS[Update Scorecard metric associations]
    end
    
    subgraph "Import vs Create Decision"
        DECISION_START[Resource Processing] --> NAME_CHECK{Check by name first}
        NAME_CHECK -->|Found| IMPORT_FLOW[Import existing ID]
        NAME_CHECK -->|Not found| CREATE_FLOW[Create new resource]
        IMPORT_FLOW --> SPEC_SYNC[Sync spec if different]
        CREATE_FLOW --> NEW_RESOURCE[Brand new resource]
    end
    
    style CHECK_BY_NAME fill:#e3f2fd
    style IMPORT_ID fill:#e8f5e8
    style UPDATE_RESOURCE fill:#fff3e0
    style TRIGGER_DEPENDENTS fill:#fce4ec
    style CASCADE_UPDATE fill:#f3e5f5
```