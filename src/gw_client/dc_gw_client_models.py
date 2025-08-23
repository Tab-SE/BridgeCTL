from dataclasses import dataclass


class UpdateCommandDto:
    def __init__(self, command_id, state, result = None, result_detail = None):
        self.command_id = command_id
        self.state = state
        self.result = result
        self.result_detail = result_detail

    def to_dict(self):
        return {
            "command_id": self.command_id,
            "state": self.state,
            "result": self.result,
            "result_detail": self.result_detail
        }


class ActionState:
    new = "new"
    started = "started"
    completed = "completed"


class ActionResults:
    success = "success"
    failed = "failed"


class GwActions:
    add_bridge_agent = "add_bridge_agent"
    remove_bridge_agent = "remove_bridge_agent"
    remove_edge_manager = "remove_edge_manager"
    # upgrade_bridge_agent = "upgrade_bridge_agent"

@dataclass
class EdgeManagerDto:
    id: int
    machine_name: str
    site_name: str = None
    os_type: str = None
    detail: dict = None

    def display_name(self):
        ot = f" ({self.os_type})" if self.os_type else ""
        return f"{self.id} - {self.machine_name}{ot}"


@dataclass
class RemoteCommand:
    id: int
    target_edge_manager_id: int
    source_edge_manager_id: int
    action: str
    state: str = None
    parameters: dict = None
    result: str = None
    result_detail: str = None
    created: str = None
    updated: str = None

    # def __init__(self, id: int, target_edge_manager_id: int, source_edge_manager_id, action, state, parameters, result, result_detail, created, updated):
    #     self.id : int = id
    #     self.target_edge_manager_id: int = target_edge_manager_id
    #     self.source_edge_manager_id: int = source_edge_manager_id
    #     self.action: str = action
    #     self.state: str = state
    #     self.parameters: dict = parameters
    #     self.result: str = result
    #     self.result_detail: str = result_detail
    #     self.created = created
    #     self.updated = updated


class Cols:
    id = 'id'
    edge_manager_id = 'edge_manager_id'
    site_luid = 'site_luid'
    site_name = 'site_name'
    os_type = 'os_type'
    detail = 'detail'
    machine_name = 'machine_name'
    created = 'created'
    updated = 'updated'
    source_edge_manager_id = 'source_edge_manager_id'
    target_edge_manager_id = 'target_edge_manager_id'
    action = 'action'
    state = 'state'
    parameters = 'parameters'
    result = 'result'
    result_detail = 'result_detail'
    gw_token = 'gw_token'
    command_id = "command_id"

class ParamNames:
    bridge_container_name = "bridge_container_name"
