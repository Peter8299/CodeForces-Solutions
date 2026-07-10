class Solution:
    def longestCommonPrefix(self, strs: List[str]) -> str:
        res=""
        strs=sorted(strs)
        f,l=strs[0],strs[-1]
        for i in range(min(len(f),len(l))):
            if f[i]!=l[i]: return res
            res+=f[i]
        return res 