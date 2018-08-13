from pyspark.ml.feature import NGram
from pyspark.sql import functions as F

from optimus.helpers.functions import collect_to_dict
from optimus.helpers.functions import parse_columns


class KeyCollision:
    """
    Taken for the amazing Open Refine post https://github.com/OpenRefine/OpenRefine/wiki/Clustering-In-Depth
    """

    def __init__(self, df):
        self.df = df

    def fingerprint(self, columns, sort_tokens=True, remove_duplicates=True):
        """
        Cluster a dataframe column based on the Fingerprint algorithm
        :param columns: Columns to be processed
        :param sort_tokens: order output values
        :param remove_duplicates: remove duplicates values
        :return:
        """
        df = self.df
        columns = parse_columns(df, columns)

        def func(value, args):
            # Split into whitespace-separated token
            split_key = value.split()

            # Sort and remove duplicated items
            sorted(set(split_key))

            # join the tokens back together
            return "".join(split_key)

        for col_name in columns:
            output_col = col_name + "_fingerprint"
            df = (df
                  .groupBy(col_name)
                  .count()
                  .select('count', col_name)
                  .withColumn(output_col, F.col(col_name))
                  .repartition(1)  # Needed for optimization in a single machine
                  .cache()
                  )

            df = (df
                  .cols.trim(output_col)
                  .cols.lower(output_col)
                  .cols.remove_special_chars(output_col)
                  .cols.remove_accents(output_col)
                  .cols.apply(output_col, func, "string", [sort_tokens, remove_duplicates])
                  .repartition(1)
                  .cache()
                  )

            # Clustering
            cluster = (df.groupBy(output_col)
                       .agg(F.count(output_col).alias("count"), F.first(F.col(col_name)).alias(col_name))
                       .sort(F.desc("count"))
                       .select(col_name, "count", F.col(output_col).alias("fingerprint"))
                       )

        return collect_to_dict(cluster.collect())

    def n_gram_fingerprint(self, column, n_size):
        """
        Cluster a DataFrame column based on the N-Gram Fingerprint algorithm
        :param column:
        :param n_size:
        :return:
        """

        output_col = column + "_ngram"
        nGramCol = column + "_ngram_fingerprint"

        df = self.df
        df = (df.select(column)
              .groupBy(column)
              .count()
              .select('count', column)
              .withColumn(output_col, F.col(column))
              .repartition(1)  # Needed for optimization in a single machine
              .cache())

        df = (df
              .cols.lower(output_col)
              .cols.remove_white_spaces(output_col)
              .cols.remove_special_chars(output_col)
              .cols.remove_accents(output_col)
              # For create n-grams we need a Array type column
              .cols.split(output_col, "")
              .repartition(1)  # Needed for optimization in a single machine
              .cache()
              )

        n_gram = NGram(n=n_size, inputCol=output_col, outputCol=nGramCol)
        df = n_gram.transform(df)

        def func(value, args):
            # remove white spaces
            value = [x.replace(" ", "") for x in value]

            # sort and remove duplicated
            value = sorted(set(value))

            # join the tokens back together
            value = "".join(value)

            return value

        df = (df
              .cols.apply(nGramCol, func, "string")
              )

        # Clustering
        cluster = (df.groupBy(nGramCol)
                   .agg(F.count(nGramCol).alias("count"), F.first(F.col(column)).alias(column))
                   .sort(F.desc("count"))
                   .select(column, "count", F.col(nGramCol).alias("fingerprint")))

        return collect_to_dict(cluster.collect())