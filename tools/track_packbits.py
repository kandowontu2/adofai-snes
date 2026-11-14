"""Minimum-size encoding for the existing SNES track CHR bytecode."""
from collections import deque

def decode(data):
    result=bytearray();i=0
    while i<len(data):
        command=data[i];i+=1;count=(command&127)+1
        if command&128:result.extend(data[i:i+1]*count);i+=1
        else:result.extend(data[i:i+count]);i+=count
    assert i==len(data)
    return bytes(result)

def encode(data):
    size=len(data);cost=[0]*(size+1);choice=[None]*size;literals=deque();run=0
    for i in range(size-1,-1,-1):
        j=i+1
        while literals and cost[literals[-1]]+literals[-1]>=cost[j]+j:literals.pop()
        literals.append(j)
        while literals[0]>i+128:literals.popleft()
        j=literals[0];best=1+j-i+cost[j];record=(False,j-i)
        run=min(128,run+1) if i+1<size and data[i]==data[i+1] else 1
        for count in range(2,run+1):
            candidate=2+cost[i+count]
            if candidate<=best:best=candidate;record=(True,count)
        cost[i]=best;choice[i]=record
    result=bytearray();i=0
    while i<size:
        repeated,count=choice[i];result.append((128 if repeated else 0)|count-1)
        result.extend(data[i:i+1] if repeated else data[i:i+count]);i+=count
    return bytes(result)
