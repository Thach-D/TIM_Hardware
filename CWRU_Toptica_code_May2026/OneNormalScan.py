import TeraScanCommands_v2 as tsc

#tsc.TestConnection()

filename = '2inch_HDPE_250401.txt'
comment = '# check if tabulation worked. \n'
with open(filename, 'a') as file:
    file.write(comment)

tsc.NormalScan(filename,150,300,0.05,80) #file, start, stop, df, itime