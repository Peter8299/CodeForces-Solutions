# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution:
    def removeElements(self, head: Optional[ListNode], val: int) -> Optional[ListNode]:
        if head is None: return 
        temp=ListNode(-1)
        temp.next=head
        cur,pos=head,temp
        while cur:
            if cur.val==val:
                pos.next=cur.next
            else:pos=cur
            cur=cur.next
        return temp.next


        