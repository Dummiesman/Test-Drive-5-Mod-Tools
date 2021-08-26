using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace td5unpack
{
    class Program
    {
        static void UnpackTexturesFile(BinaryReader reader, string outDir)
        {
            long baseOffset = reader.BaseStream.Position;
            int numChunks = reader.ReadInt32();

            List<int> offsets = new List<int>(numChunks);
            for (int i = 0; i < numChunks; i++)
            {
                int offset = reader.ReadInt32();
                offsets.Add(offset);
            }

            for(int i=0; i < numChunks; i++)
            {
                Console.WriteLine($"\ttexture {i+1}/{numChunks}");

                //seek to tex
                reader.BaseStream.Seek(baseOffset + offsets[i], SeekOrigin.Begin);

                //read and output
                byte b1 = reader.ReadByte();
                byte b2 = reader.ReadByte();
                short texflags = reader.ReadInt16();
                if (b1 != 6 || b2 != 6)
                {
                    Console.WriteLine($"Unknown texture header? @{reader.BaseStream.Position}, {b1} {b2}");
                }

                bool blackChromaKey = (texflags & 256) != 0;
                bool alwaysSetFlag = (texflags & 1) != 0;
                bool additiveBlendFlag = (texflags & 512) != 0;

                int palSize = reader.ReadInt32();
                List<Color> pal = new List<Color>(palSize);
                for (int j = 0; j < palSize; j++)
                {
                    byte cb = reader.ReadByte();
                    byte cg = reader.ReadByte();
                    byte cr = reader.ReadByte();

                    byte ca = 255;
                    if (blackChromaKey && (cb == 0 && cg == 0 && cr == 0))
                    {
                        ca = 0;
                    }

                    pal.Add(Color.FromArgb(ca, cr, cg, cb));
                }

                //all images are 64x64
                Bitmap b = new Bitmap(64, 64, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
                for (int y = 0; y < 64; y++)
                {
                    for (int x = 0; x < 64; x++)
                    {
                        byte index = reader.ReadByte();
                        b.SetPixel(x, y, pal[index]);
                    }
                }

                //save
                string savePath = Path.Combine(outDir, $"texture_{i}.png");
                b.Save(savePath, System.Drawing.Imaging.ImageFormat.Png);
                b.Dispose();
            }

        }

        static void UnpackModelsFile(BinaryReader reader, string outDir)
        {
            long baseOffset = reader.BaseStream.Position;
            int numChunks = reader.ReadInt32();

            List<int> offsets = new List<int>(numChunks);
            List<int> sizes = new List<int>(numChunks);

            for (int i = 0; i < numChunks; i++)
            {
                int offset = reader.ReadInt32();
                int size = reader.ReadInt32();

                offsets.Add(offset);
                sizes.Add(size);
            }

            for (int i = 0; i < numChunks; i++)
            {
                Console.WriteLine($"\tmodel group {i + 1}/{numChunks}");

                int offset = offsets[i];
                int size = sizes[i];

                reader.BaseStream.Seek(baseOffset + offset, SeekOrigin.Begin);

                //read and unpack sub models
                //we read one extra here because TD6 has a 0 in front of the list
                //and we probably will never overrun a file doing this
                int numModels = reader.ReadInt32();

                List<int> modelOffsets = new List<int>(numModels + 1);
                for (int j = 0; j < numModels + 1; j++)
                    modelOffsets.Add(reader.ReadInt32());

                if (modelOffsets[0] == 0 || modelOffsets[0] == 1) // TD6
                    modelOffsets.RemoveAt(0);
                else
                    modelOffsets.RemoveAt(modelOffsets.Count - 1);

                for (int j = 0; j < numModels; j++)
                {
                    bool isLast = (j == numModels - 1);
                    int modelOffset = modelOffsets[j];
                    int modelSize = (isLast) ? size - modelOffset : (modelOffsets[j + 1] - modelOffset);
                    long modelTotalOffset = baseOffset + offset + modelOffset;

                    reader.BaseStream.Seek(modelTotalOffset, SeekOrigin.Begin);

                    string outPath = Path.Combine(outDir, $"{modelTotalOffset:X4}.dat");
                    byte[] data = reader.ReadBytes(modelSize);
                    File.WriteAllBytes(outPath, data);
                }
            }

        }

        static void Main(string[] args)
        {
            Console.Title = "TD5Unpack";

            Console.WriteLine($"td5unpack");
            Console.WriteLine($"Unpacks Test Drive 5 textures.dat/models.dat files");
            Console.WriteLine($"Textures are converted to PNG. Models are extracted in their raw form");
            Console.WriteLine($"Created by Dummiesman");
            Console.WriteLine($"=========================================================");

            if(args.Length == 0)
            {
                Console.WriteLine($"No input file was given.");
                Console.Read();
                return;
            }


            string filepath = args[0];
            if (!File.Exists(filepath))
            {
                Console.WriteLine($"Input file does not exist.");
                Console.Read();
                return;
            }

            string filename = Path.GetFileNameWithoutExtension(filepath).ToLower();
            if(filename != "textures" && filename != "models")
            {
                Console.WriteLine($"I don't know how to unpack {filename}");
                Console.Read();
                return;
            }

            //create output dir
            if (!Directory.Exists(filename))
            {
                Directory.CreateDirectory(filename);
            }

            //unpack
            Console.WriteLine($"Unpacking {filename}");
            using (var reader = new BinaryReader(File.OpenRead(filepath)))
            {
                if (filename == "textures")
                {
                    UnpackTexturesFile(reader, filename);
                }
                else if (filename == "models")
                {
                    UnpackModelsFile(reader, filename);
                }
            }
        }
    }
}
