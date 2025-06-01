from random import *
from sys import *
while True:
                class main:
                    def __init__(self,number_guessed):
                        self.number_guesed=number_guessed
                    def run(self):
                        pass
                print("chose a number from 1 to 30")
                number_check=int(input("type number guessed:   "))
                num_val=main(number_guessed=number_check)
                #print(num_val.number_guesed)
                num_holder=[]
                num_holder.append(num_val.number_guesed)
                valid_num=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
                choser=sample(valid_num,k=1)[0]
                print(choser)
                if choser==valid_num[0]:
                            print("ok")
                            print(num_holder,end=" ");print("valid")
                            break
                else:
                    print("error")