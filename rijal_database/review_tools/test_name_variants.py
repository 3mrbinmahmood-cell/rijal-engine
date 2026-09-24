import unittest

from rijal_database.review_tools.name_variants import signature


class VariantSignatureTests(unittest.TestCase):
    def test_kunya_case_and_orthographic_variants(self):
        self.assertEqual(signature('أبو عبد الله بن رفاعة'),
                         signature('أبي عبدالله بن رفاعه'))
        self.assertEqual(signature('الرؤاسي'),signature('الرواسي'))

    def test_different_genealogy_stays_separate(self):
        self.assertNotEqual(signature('محمد بن أحمد بن علي'),
                            signature('محمد بن أحمد بن عمر'))


if __name__=='__main__':unittest.main()
