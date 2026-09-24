import unittest

from rijal_database.review_tools.relationship_candidates import relationships


class RelationshipExtractionTests(unittest.TestCase):
    def test_teacher_and_student_lists_keep_separate_roles(self):
        text=('روى عن: إبراهيم التيمي، وخيثمة بن عبد الرحمن. '
              'روى عنه: عبد الأعلى بن حماد، وأبو داود الطيالسي.')
        result=relationships(text)
        self.assertIn('ابراهيم التيمي',result['teachers'])
        self.assertIn('خيثمة بن عبد الرحمن',result['teachers'])
        self.assertIn('عبد الاعلي بن حماد',result['students'])
        self.assertNotIn('عبد الاعلي بن حماد',result['teachers'])

    def test_students_do_not_become_teachers_from_prefix(self):
        result=relationships('روى عنه ابن الغسيل. وله أخبار أخرى.')
        self.assertEqual(result['teachers'],set())
        self.assertIn('ابن الغسيل',result['students'])


if __name__=='__main__':unittest.main()
