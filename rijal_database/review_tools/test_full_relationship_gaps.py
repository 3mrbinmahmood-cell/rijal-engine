import json
import unittest

from rijal_database.review_tools.full_relationship_gaps import ranked_pairs


class RelationshipGapTest(unittest.TestCase):
    def test_overlap_does_not_merge_and_skips_same_identity(self):
        def clues(teachers,students):
            return {'teachers':set(teachers),'students':set(students)}
        entries=[('a','person','book1',clues(['teacher1','teacher2'],['student1'])),
                 ('b','candidate','book2',clues(['teacher1','teacher2'],['student1'])),
                 ('c','person','book3',clues(['other teacher'],['other student']))]
        pairs=ranked_pairs(entries,'bucket')
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0][:3],('a','b','bucket'))
        self.assertEqual(json.loads(pairs[0][7]),['teacher1','teacher2'])
        self.assertEqual(pairs[0][-1],'both_lists_3plus')
        self.assertEqual(ranked_pairs([entries[0],
            ('c','person','book3',clues(['teacher1'],['student1']))],
            'bucket'),[])


if __name__=='__main__':unittest.main()
