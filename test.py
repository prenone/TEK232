with open("/dev/usbtmc0", "r+") as file:
    file.write("ID?\n")
    print(file.readline())