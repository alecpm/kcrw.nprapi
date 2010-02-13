import unittest
import doctest

def test_suite():
    doctests = ('story.txt', 'story.txt')
    return unittest.TestSuite([
        doctest.DocFileSuite(test,
                             optionflags=doctest.ELLIPSIS,
                             package='kcrw.nprapi')
        for test in doctests
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
