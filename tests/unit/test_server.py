from yandex_tracker_mcp.server import mcp


class TestMcpTools:
    def test_tools__registered__include_read_write_and_links(self) -> None:
        # act
        names = {tool.name for tool in mcp._tool_manager.list_tools()}

        # assert
        assert names == {
            'get_issue',
            'create_issue',
            'update_issue',
            'get_epic_issues',
            'get_project_epics',
            'get_issue_links',
            'link_issue',
            'get_comments',
            'create_comment',
            'update_comment',
        }
