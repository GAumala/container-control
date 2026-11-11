import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "container_control.py"
spec = importlib.util.spec_from_file_location("container_control", MODULE_PATH)
controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = controller
spec.loader.exec_module(controller)


class ParseRequestTests(unittest.TestCase):
    def test_list_includes_all_containers(self):
        self.assertEqual(
            controller.parse_request(["list"]),
            ["/usr/bin/docker", "ps", "--all", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
        )

    def test_logs_is_bounded(self):
        self.assertEqual(
            controller.parse_request(["logs", "jellyfin", "50"]),
            ["/usr/bin/docker", "logs", "--tail", "50", "--timestamps", "jellyfin"],
        )

    def test_allows_valid_container_id(self):
        self.assertEqual(controller.parse_request(["restart", "a4e7c0"]), ["/usr/bin/docker", "restart", "a4e7c0"])

    def test_disallows_option_like_name(self):
        with self.assertRaises(controller.RequestError):
            controller.parse_request(["restart", "--privileged"])

    def test_disallows_extra_arguments(self):
        with self.assertRaises(controller.RequestError):
            controller.parse_request(["logs", "jellyfin", "2", "--follow"])

    def test_disallows_too_many_log_lines(self):
        with self.assertRaises(controller.RequestError):
            controller.parse_request(["logs", "jellyfin", "501"])


if __name__ == "__main__":
    unittest.main()
