from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from forum.models import Block, Course


class ImportBlockMappingsCommandTests(TestCase):
    def write_mapping(self, contents):
        temp_dir = TemporaryDirectory()
        path = Path(temp_dir.name) / "mappings.txt"
        path.write_text(contents, encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def test_course_name_may_contain_a_colon(self):
        Block.objects.create(code="1B")
        Course.objects.create(name="AP World History: Modern")
        mapping_path = self.write_mapping("AP World History: Modern: 1B\n")

        call_command("import_block_mappings", str(mapping_path), dry_run=True, stdout=StringIO())

        comparison_path = mapping_path.with_name("mappings.dry-run.txt")
        self.assertIn("AP World History: Modern: 1B", comparison_path.read_text(encoding="utf-8"))

    def test_dry_run_writes_comparison_file_without_changing_mappings(self):
        block = Block.objects.create(code="1B")
        course = Course.objects.create(name="Current Course")
        course.blocks.add(block)
        new_course = Course.objects.create(name="New Course")
        mapping_path = self.write_mapping("New Course: 1B\n")
        output_path = mapping_path.with_name("comparison.txt")

        call_command(
            "import_block_mappings",
            str(mapping_path),
            dry_run=True,
            dry_run_output=str(output_path),
        )

        comparison = output_path.read_text(encoding="utf-8")
        self.assertIn("New Course: 1B", comparison)
        self.assertIn("# COURSES_NOT_ADDED: existing Course objects not represented in the staged mappings", comparison)
        self.assertIn("# Current Course", comparison)
        self.assertEqual(list(course.blocks.values_list("code", flat=True)), ["1B"])
        self.assertEqual(list(new_course.blocks.values_list("code", flat=True)), [])

    def test_apply_replaces_all_existing_mappings(self):
        old_block = Block.objects.create(code="1A")
        new_block = Block.objects.create(code="2C")
        old_course = Course.objects.create(name="Old Course")
        old_course.blocks.add(old_block)
        new_course = Course.objects.create(name="New Course")
        mapping_path = self.write_mapping("New Course: 2C\n")

        call_command("import_block_mappings", str(mapping_path))

        self.assertEqual(list(old_course.blocks.values_list("code", flat=True)), [])
        self.assertEqual(list(new_course.blocks.values_list("code", flat=True)), ["2C"])

    def test_apply_refuses_to_clear_when_a_mapping_is_unresolved(self):
        old_block = Block.objects.create(code="1A")
        old_course = Course.objects.create(name="Old Course")
        old_course.blocks.add(old_block)
        mapping_path = self.write_mapping("Missing Course: 2C\n")

        with self.assertRaises(CommandError):
            call_command("import_block_mappings", str(mapping_path))

        self.assertEqual(list(old_course.blocks.values_list("code", flat=True)), ["1A"])

    def test_dry_run_lists_courses_that_were_not_added(self):
        Block.objects.create(code="2C")
        mapping_path = self.write_mapping("Missing Course: 2C\n")
        output = StringIO()

        call_command("import_block_mappings", str(mapping_path), dry_run=True, stdout=output)

        self.assertIn("Not added:", output.getvalue())
        self.assertIn("'Missing Course' -> ['2C'] : COURSE_NOT_FOUND", output.getvalue())
